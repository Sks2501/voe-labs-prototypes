"""Bounded single-worker CPU inference; no downloads or remote calls at runtime."""
from __future__ import annotations
from dataclasses import dataclass, field
import ctypes
import os
from pathlib import Path
import queue
import threading
import time
from .settings import DEFAULT_MODEL, MAX_INPUT_TOKENS, MAX_NEW_TOKENS, MODELS, DATA_DIR


class InferenceUnavailable(RuntimeError):
    pass


class InferenceBusy(InferenceUnavailable):
    pass


class InferenceTimeout(InferenceUnavailable):
    pass


def _integer_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(name + " is outside permitted bounds")
    return value


def available_memory_bytes() -> int:
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except ImportError:
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total", ctypes.c_ulonglong), ("available", ctypes.c_ulonglong),
                            ("page_total", ctypes.c_ulonglong), ("page_available", ctypes.c_ulonglong),
                            ("virtual_total", ctypes.c_ulonglong), ("virtual_available", ctypes.c_ulonglong),
                            ("extended", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                raise InferenceUnavailable("Unable to inspect available memory")
            return status.available
        return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))


def build_prompt(message: str, history: list[dict], memories: list[dict]) -> str:
    if not isinstance(message, str) or not message.strip() or len(message) > 2400:
        raise ValueError("Message must contain between 1 and 2400 characters")
    words = {word.lower().strip(".,!?;:") for word in message.split() if len(word) > 3}
    relevant = [item.get("content", "")[:160] for item in memories[:100]
                if words.intersection(item.get("content", "").lower().split())][:3]
    parts = ["SEXTA-FEIRA é uma assistente pessoal experimental. Responde em português brasileiro.",
             "Uma resposta gerada não comprova execução de ações nem veracidade de fatos."]
    if relevant:
        parts.append("Memórias explicitamente salvas: " + " | ".join(relevant))
    for item in history[-4:]:
        role = "Usuário" if item.get("role") == "user" else "SEXTA-FEIRA"
        parts.append(role + ": " + str(item.get("content", ""))[:240])
    parts.extend(("Usuário: " + message.strip(), "SEXTA-FEIRA:"))
    return "\n".join(parts)


@dataclass
class _Job:
    prompt: str
    model_size: str
    deadline: float
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    result: str | None = None
    error: Exception | None = None


class InferenceEngine:
    def __init__(self):
        self._load_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._model = None
        self._model_size = None
        self._loading = False
        self._closed = threading.Event()
        self._thread = None
        self._queue = queue.Queue(maxsize=_integer_setting("SEXTA_QUEUE_LIMIT", 2, 1, 8))
        self._active = None
        self._failures = self._requests = self._generated = 0
        self._last_seconds = self._last_error = None
        self._cooldown_until = 0.0
        self._timeout = _integer_setting("SEXTA_INFERENCE_TIMEOUT", 60, 5, 180)
        self._threads = _integer_setting("SEXTA_CPU_THREADS", 1, 1, min(2, os.cpu_count() or 1))
        self._reserve_mb = _integer_setting("SEXTA_MEMORY_RESERVE_MB", 1024, 512, 8192)
        self._input_limit = min(512, MAX_INPUT_TOKENS)
        self._output_limit = min(64, MAX_NEW_TOKENS)

    def _memory_guard(self, *, loading=False, model_size="small"):
        allocation = (900 if model_size == "small" else 2100) if loading else 96
        if available_memory_bytes() < (self._reserve_mb + allocation) * 1024 * 1024:
            raise InferenceUnavailable("Insufficient available RAM; production reserve protected")

    def load(self, model_size=DEFAULT_MODEL):
        if model_size not in ("small", "medium") or model_size not in MODELS:
            raise ValueError("Use small (124M) or explicitly selected medium (355M)")
        with self._load_lock:
            if self._closed.is_set():
                raise InferenceUnavailable("Inference engine is closed")
            if self._model is not None:
                if model_size != self._model_size:
                    raise InferenceUnavailable("Restart required to change model; duplicate instances forbidden")
                return self._model.tokenizer, self._model
            self._memory_guard(loading=True, model_size=model_size)
            directory = Path(os.environ.get("SEXTA_MODEL_DIR") or (DATA_DIR / "models")) / (
                "124M" if model_size == "small" else "355M")
            if not (directory / "integrity.json").is_file():
                raise InferenceUnavailable("Verified local checkpoint missing; run the official weight downloader")
            self._loading = True
            try:
                from .inference_torch import GPT2CPU
                model = GPT2CPU(directory, self._threads)
                if self._closed.is_set():
                    raise InferenceUnavailable("Inference engine closed during initialization")
                self._model, self._model_size = model, model_size
                self._last_error = None
                return model.tokenizer, model
            except Exception as exc:
                self._last_error = type(exc).__name__
                raise InferenceUnavailable("Local GPT-2 initialization failed; inspect protected diagnostics") from exc
            finally:
                self._loading = False

    def submit(self, prompt: str, model_size: str, cancel_event=None, timeout=None) -> str:
        if cancel_event is not None and cancel_event.is_set():
            raise InferenceTimeout("Inference request was already cancelled")
        timeout = self._timeout if timeout is None else timeout
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= self._timeout:
            raise ValueError("Invalid inference timeout")
        with self._state_lock:
            if self._closed.is_set():
                raise InferenceUnavailable("Inference engine is closed")
            if time.monotonic() < self._cooldown_until:
                raise InferenceUnavailable("Inference is cooling down after repeated failures")
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="sexta-inference", daemon=True)
                self._thread.start()
            job = _Job(prompt, model_size, time.monotonic() + timeout)
            try:
                self._queue.put_nowait(job)
            except queue.Full as exc:
                raise InferenceBusy("Inference queue is full") from exc
            self._requests += 1
        while not job.done.wait(min(0.1, timeout)):
            if (cancel_event is not None and cancel_event.is_set()) or time.monotonic() >= job.deadline:
                job.cancel.set()
                raise InferenceTimeout("Inference request expired or was cancelled")
        if job.error is not None:
            raise job.error
        return job.result

    def _run(self):
        while not self._closed.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._active = job
            started = time.monotonic()
            def check():
                if self._closed.is_set() or job.cancel.is_set() or time.monotonic() >= job.deadline:
                    raise InferenceTimeout("Inference request expired or was cancelled")
                self._memory_guard()
            try:
                check()
                _, model = self.load(job.model_size)
                check()
                result, count = model.generate(job.prompt, input_limit=self._input_limit,
                                               new_tokens=self._output_limit, cancelled=check)
                check()
                for delimiter in ("\nUsuário:", "\nSEXTA-FEIRA:", "\nUser:", "\nAssistant:"):
                    result = result.split(delimiter, 1)[0].strip()
                job.result = result[:1200] or "Não consegui gerar uma resposta útil. Pode reformular a pergunta?"
                self._generated += count
                self._failures = 0
            except Exception as exc:
                job.error = exc if isinstance(exc, (InferenceUnavailable, ValueError)) else InferenceUnavailable(
                    "Local inference failed; no external inference was attempted")
                self._last_error = type(exc).__name__
                if not isinstance(exc, InferenceTimeout):
                    self._failures += 1
                    if self._failures >= 3:
                        self._cooldown_until = time.monotonic() + 60
            finally:
                self._last_seconds = round(time.monotonic() - started, 3)
                self._active = None
                job.done.set()
                self._queue.task_done()
        self._model = None

    def status(self):
        return {"model": self._model_size or DEFAULT_MODEL, "loaded": self._model is not None,
                "loading": self._loading, "device": "cpu", "cpu_threads": self._threads,
                "context_tokens": self._input_limit, "max_new_tokens": self._output_limit,
                "queue_depth": self._queue.qsize(), "queue_limit": self._queue.maxsize,
                "processing": self._active is not None, "requests": self._requests,
                "generated_tokens": self._generated, "last_seconds": self._last_seconds,
                "consecutive_failures": self._failures,
                "cooldown_seconds": max(0, round(self._cooldown_until - time.monotonic())),
                "last_error_type": self._last_error, "closed": self._closed.is_set(),
                "memory_reserve_mb": self._reserve_mb, "local_only": True}

    def close(self):
        with self._state_lock:
            self._closed.set()
            if self._active is not None:
                self._active.cancel.set()
            while True:
                try:
                    job = self._queue.get_nowait()
                except queue.Empty:
                    break
                job.error = InferenceUnavailable("Inference engine is shutting down")
                job.done.set()
                self._queue.task_done()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._thread is None or not self._thread.is_alive():
            self._model = None


_ENGINE = None
_ENGINE_LOCK = threading.Lock()


def _get_engine():
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            backend = os.environ.get("SEXTA_BACKEND", "gpt2")
            if backend == "llama.cpp":
                from .inference_llama import LocalChatEngine
                _ENGINE = LocalChatEngine()
            elif backend == "gpt2":
                _ENGINE = InferenceEngine()
            else:
                raise ValueError("Unknown inference backend")
        return _ENGINE


def load_model(model_size: str = DEFAULT_MODEL):
    return _get_engine().load(model_size)


def generate_reply(message: str, history: list[dict], memories: list[dict], model_size: str = DEFAULT_MODEL,
                   *, cancel_event=None, timeout=None) -> str:
    engine = _get_engine()
    if getattr(engine, "backend", None) == "llama.cpp":
        return engine.submit(engine.build_messages(message, history, memories), model_size, cancel_event, timeout)
    return engine.submit(build_prompt(message, history, memories), model_size, cancel_event, timeout)


def generated_source():
    return "local_model" if os.environ.get("SEXTA_BACKEND", "gpt2") == "llama.cpp" else "gpt2"


def engine_status():
    return _get_engine().status()


def shutdown_engine():
    if _ENGINE is not None:
        _ENGINE.close()
