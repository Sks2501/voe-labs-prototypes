"""Private DACL for this application's data directory only; no global ACL changes."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path


def protect_data_directory(directory: Path) -> None:
    original = Path(directory)
    if original.is_symlink() or (hasattr(original, "is_junction") and original.is_junction()):
        raise ValueError("A pasta de dados deve ser local, sem redirecionamento.")
    directory = original.resolve()
    if directory in (Path(directory.anchor), Path.home().resolve(), Path.cwd().resolve()):
        raise ValueError("Escolha uma pasta de dados exclusiva da SEXTA-FEIRA.")
    marker = directory / ".sexta-data"
    if directory.exists() and any(directory.iterdir()):
        if not marker.is_file() or marker.is_symlink() or marker.read_text(encoding="utf-8").strip() != "sexta-feira-data-v1":
            raise ValueError("Pasta não identificada como dados da SEXTA-FEIRA; conteúdo e permissões preservados. Use uma pasta nova e migre por backup.")
    directory.mkdir(parents=True, exist_ok=True)
    # Validate the whole owned tree before changing any ACL; never follow links.
    owned = [directory]
    for parent, folders, files in os.walk(directory, followlinks=False):
        for name in folders + files:
            item = Path(parent) / name
            if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                raise ValueError("Redirecionamento encontrado nos dados; permissões preservadas.")
            owned.append(item)
    if os.name != "nt":
        directory.chmod(0o700)
        for item in owned[1:]:
            item.chmod(0o700 if item.is_dir() else 0o600)
        marker.write_text("sexta-feira-data-v1\n", encoding="utf-8")
        return
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR,
        wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    advapi.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    advapi.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    advapi.SetNamedSecurityInfoW.restype = wintypes.DWORD
    token, sid_string, descriptor = wintypes.HANDLE(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, buffer, needed.value, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.c_void_p.from_buffer(buffer).value
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_string)):
            raise ctypes.WinError(ctypes.get_last_error())
        current_sid = ctypes.wstring_at(sid_string)
        sddl = ("D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
                f"(A;OICI;FA;;;{current_sid})(A;OICI;0x1301bf;;;LS)")
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        present, defaulted, dacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        if not advapi.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present),
                                                ctypes.byref(dacl), ctypes.byref(defaulted)):
            raise ctypes.WinError(ctypes.get_last_error())
        for item in owned:
            result = advapi.SetNamedSecurityInfoW(str(item), 1, 0x80000004,
                                                  None, None, dacl, None)
            if result:
                raise ctypes.WinError(result)
        marker.write_text("sexta-feira-data-v1\n", encoding="utf-8")
    finally:
        if descriptor.value:
            kernel.LocalFree(descriptor)
        if sid_string.value:
            kernel.LocalFree(sid_string)
        if token.value:
            kernel.CloseHandle(token)
