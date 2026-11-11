"""WinSW child supervising one offline, CPU-only llama.cpp process."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from service_runner import kernel

EVENT = "Local\\SextaFeiraNativeStop"


def main():
    api = kernel()
    if len(sys.argv) == 2 and sys.argv[1] == "stop":
        handle = api.OpenEventW(0x0002, False, EVENT)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not api.SetEvent(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            api.CloseHandle(handle)
        return 0
    if len(sys.argv) != 3 or sys.argv[1] != "run":
        raise ValueError("Usage: native_runner.py run <private-config> | stop")
    config = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
    root = Path(config["data_dir"]).parent
    directory = root / "local-model"
    binary_directory = directory / "llama-b12282"
    receipt = json.loads((binary_directory / ".sexta-llama.json").read_text())
    for name, expected in receipt["files"].items():
        path = (binary_directory / name).resolve()
        if not path.is_relative_to(binary_directory.resolve()):
            raise ValueError("Native executable path escaped its directory")
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Native executable integrity mismatch")
    model = directory / "gemma-3-4b-it-Q4_K_M.gguf"
    with model.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863":
        raise ValueError("Pinned local model integrity mismatch")
    from sexta_feira.brain import available_memory_bytes
    if available_memory_bytes() < 5 * 1024**3:
        raise MemoryError("Native model startup requires 5 GiB free, including production reserve")
    handle = api.CreateEventW(None, True, False, EVENT)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        api.CloseHandle(handle)
        raise RuntimeError("A native model runner is already active")
    child = None
    stopped = threading.Event()
    try:
        args = [str(binary_directory / "llama-server.exe"), "-m", str(model),
                "--host", "127.0.0.1", "--port", "18765", "-ngl", "0", "-t", "2", "-tb", "2",
                "-c", "2048", "-np", "1", "-n", "192", "-b", "128", "-ub", "64",
                "--poll", "0", "--poll-batch", "0", "--alias", "sexta-local", "--api-key-file",
                config["native_token_file"], "--no-webui", "--offline", "--log-disable"]
        child = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        record = {"pid": child.pid, "executable": args[0], "started_unix": time.time()}
        (root / "data" / "inference-process.json").write_text(json.dumps(record), encoding="utf-8")
        def wait_stop():
            api.WaitForSingleObject(handle, 0xFFFFFFFF)
            stopped.set()
        thread = threading.Thread(target=wait_stop, daemon=True)
        thread.start()
        while child.poll() is None and not stopped.wait(0.25):
            pass
        if stopped.is_set():
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            return 0
        print("native_inference_exit code=" + str(child.returncode), flush=True)
        return child.returncode or 1
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)
        api.SetEvent(handle)
        api.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
