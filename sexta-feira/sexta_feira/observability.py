"""Bounded operational logs and content-free process/resource metrics."""
from __future__ import annotations

import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import threading
import time

_STARTED = time.monotonic()
_SAMPLE_LOCK = threading.Lock()
_PREVIOUS = None
_NATIVE_PREVIOUS = None


def native_resource_snapshot(data_dir: Path) -> dict:
    """Read only the verified native model process, without exposing its PID/path."""
    if os.name != "nt":
        return {}
    try:
        record = json.loads((data_dir / "inference-process.json").read_text(encoding="utf-8"))
        pid = int(record["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return {}
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        expected = data_dir.parent / "local-model" / "llama-b12282" / "llama-server.exe"
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return {}
        if Path(buffer.value).resolve() != expected.resolve():
            return {}
        class ProcessMemory(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (key, ctypes.c_size_t) for key in ("peak_working","working","peak_paged","paged",
                "peak_nonpaged","nonpaged","pagefile","peak_pagefile")]
        memory = ProcessMemory()
        memory.cb = ctypes.sizeof(memory)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            return {}
        result = {"inference_process_rss_bytes": memory.working,
                  "inference_process_peak_rss_bytes": memory.peak_working}
        times = [wintypes.FILETIME() for _ in range(4)]
        if kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            cpu = sum((t.dwHighDateTime << 32) + t.dwLowDateTime for t in times[2:]) / 10_000_000
            now = time.monotonic()
            global _NATIVE_PREVIOUS
            with _SAMPLE_LOCK:
                previous, _NATIVE_PREVIOUS = _NATIVE_PREVIOUS, (pid, now, cpu)
            result["inference_process_cpu_seconds"] = round(cpu, 3)
            result["inference_process_cpu_percent"] = None
            if previous and previous[0] == pid and now > previous[1]:
                result["inference_process_cpu_percent"] = round(max(0,min(100,
                    (cpu-previous[2])/(now-previous[1])*100/(os.cpu_count() or 1))),2)
        return result
    finally:
        kernel.CloseHandle(handle)


def configure_logging(data_dir: Path) -> None:
    logger = logging.getLogger("sexta_feira")
    if logger.handlers:
        return
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "operations.log", maxBytes=1_048_576,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def resource_snapshot(data_dir: Path | None = None) -> dict:
    """No addresses, filenames, environment, credentials or message content."""
    global _PREVIOUS
    sampled_at, process_cpu = time.monotonic(), time.process_time()
    with _SAMPLE_LOCK:
        previous, _PREVIOUS = _PREVIOUS, (sampled_at, process_cpu)
    result = {"uptime_seconds": round(sampled_at - _STARTED, 2),
              "cpu_logical": os.cpu_count() or 1,
              "process_cpu_seconds": round(process_cpu, 3),
              "process_cpu_percent": None}
    if previous and sampled_at > previous[0]:
        result["process_cpu_percent"] = round(min(100, max(0,
            (process_cpu - previous[1]) / (sampled_at - previous[0]) * 100 /
            (os.cpu_count() or 1))), 2)
    if data_dir is not None:
        try:
            usage = shutil.disk_usage(data_dir)
            result.update(disk_free_bytes=usage.free, disk_total_bytes=usage.total)
        except OSError:
            pass
    if os.name == "nt":
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (key, ctypes.c_ulonglong) for key in
                ("total_physical", "available_physical", "total_page", "available_page",
                 "total_virtual", "available_virtual", "extended")]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            result.update(ram_total_bytes=status.total_physical,
                          ram_available_bytes=status.available_physical,
                          ram_used_percent=status.load)

        class ProcessMemory(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (key, ctypes.c_size_t) for key in
                ("peak_working", "working", "peak_paged", "paged", "peak_nonpaged",
                 "nonpaged", "pagefile", "peak_pagefile")]

        process = ProcessMemory()
        process.cb = ctypes.sizeof(process)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(process), process.cb):
            result.update(process_rss_bytes=process.working,
                          process_peak_rss_bytes=process.peak_working)
    return result
