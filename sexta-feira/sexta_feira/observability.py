"""Bounded operational logs and content-free process/resource metrics."""
from __future__ import annotations

import ctypes
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
