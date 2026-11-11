"""Private WinSW child process with a Windows event for graceful shutdown.

The named event lives in the Windows session of the service. WinSW runs the
stop command with the same service identity; no public administrative endpoint
or command interpreter is exposed.
"""
from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVENT_NAME = "Local\\SextaFeiraServiceStop"

def kernel():
    if os.name != "nt":
        raise RuntimeError("Windows service runner requires Windows.")
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateEventW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
    api.CreateEventW.restype = wintypes.HANDLE
    api.OpenEventW.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.LPCWSTR]
    api.OpenEventW.restype = wintypes.HANDLE
    api.SetEvent.argtypes = [wintypes.HANDLE]
    api.SetEvent.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    return api

def main():
    api=kernel()
    if len(sys.argv) == 2 and sys.argv[1] == "stop":
        handle=api.OpenEventW(0x0002,False,EVENT_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not api.SetEvent(handle): raise ctypes.WinError(ctypes.get_last_error())
        finally: api.CloseHandle(handle)
        return
    if len(sys.argv) != 3 or sys.argv[1] != "run":
        raise SystemExit("Usage: service_runner.py run <private-config.json> | stop")
    config=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
    os.environ["SEXTA_DATA_DIR"]=config["data_dir"]
    os.environ["SEXTA_MODEL_DIR"]=config["model_dir"]
    os.environ["SEXTA_OFFLINE"]="1"
    os.environ["SEXTA_BACKEND"]=config.get("backend", "gpt2")
    os.environ["SEXTA_TEMPERATURE_FILE"]=str(Path(sys.argv[2]).resolve().parent / "sensors" / "temperatures.json")
    for field, variable in (("native_url", "SEXTA_NATIVE_URL"), ("native_token_file", "SEXTA_NATIVE_TOKEN_FILE"),
                            ("history_after_id", "SEXTA_HISTORY_AFTER_ID")):
        if field in config: os.environ[variable]=str(config[field])
    from sexta_feira.observability import configure_logging
    configure_logging(Path(config["data_dir"]))
    from sexta_feira.server import AssistantServer
    from sexta_feira.storage import Storage
    from sexta_feira.brain import shutdown_engine
    token=(Path(config["data_dir"])/"access.token").read_text(encoding="utf-8").strip()
    if len(token) < 32: raise RuntimeError("Private access token is missing or invalid.")
    handle=api.CreateEventW(None,True,False,EVENT_NAME)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    # Refuse a duplicate runner sharing the same event instead of clearing it.
    if ctypes.get_last_error() == 183:
        api.CloseHandle(handle)
        raise RuntimeError("Another SEXTA-FEIRA service runner is already active.")
    try:
        with AssistantServer(("127.0.0.1",int(config["port"])),token,"small",Storage(), public_origin=config.get("public_origin")) as server:
            def wait_stop():
                api.WaitForSingleObject(handle,0xFFFFFFFF)
                server.shutdown()
            thread=threading.Thread(target=wait_stop,name="windows-stop",daemon=True)
            thread.start()
            try: server.serve_forever(poll_interval=0.25)
            finally:
                api.SetEvent(handle)
                shutdown_engine()
                thread.join(timeout=3)
    finally: api.CloseHandle(handle)

if __name__ == "__main__": main()
