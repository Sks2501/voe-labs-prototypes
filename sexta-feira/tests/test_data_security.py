"""Real filesystem checks for private data-directory initialization."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from sexta_feira.windows_security import protect_data_directory


class DataDirectoryTests(unittest.TestCase):
    def test_refuses_unowned_directory_without_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample = root / "unrelated.txt"
            sample.write_text("preserve", encoding="utf-8")
            before = root.stat().st_mode
            with self.assertRaises(ValueError):
                protect_data_directory(root)
            self.assertEqual(sample.read_text(encoding="utf-8"), "preserve")
            self.assertEqual(root.stat().st_mode, before)
            self.assertFalse((root / ".sexta-data").exists())

    def test_repeated_protection_preserves_owned_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "data"
            protect_data_directory(root)
            (root / "access.token").write_text("public-test-placeholder", encoding="utf-8")
            protect_data_directory(root)
            self.assertEqual((root / "access.token").read_text(encoding="utf-8"), "public-test-placeholder")
            self.assertEqual((root / ".sexta-data").read_text(encoding="utf-8").strip(), "sexta-feira-data-v1")

    @unittest.skipUnless(os.name == "nt", "Windows DACL test")
    def test_existing_explicit_world_read_is_removed(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "data"
            protect_data_directory(root)
            token = root / "access.token"
            token.write_text("public-test-placeholder", encoding="utf-8")
            subprocess.run(["icacls.exe", str(token), "/grant", "*S-1-1-0:R"],
                           check=True, stdout=subprocess.DEVNULL)
            protect_data_directory(root)
            api = ctypes.WinDLL("advapi32", use_last_error=True)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            api.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p)]
            api.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [ctypes.c_void_p,
                wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
            descriptor, text = ctypes.c_void_p(), ctypes.c_void_p()
            try:
                self.assertEqual(api.GetNamedSecurityInfoW(str(token), 1, 4, None, None, None,
                    None, ctypes.byref(descriptor)), 0)
                self.assertTrue(api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    descriptor, 1, 4, ctypes.byref(text), None))
                sddl = ctypes.wstring_at(text)
                self.assertIn("D:P", sddl)
                self.assertNotIn(";;;WD)", sddl)
                self.assertNotIn(";;;BU)", sddl)
                self.assertNotIn(";;;AU)", sddl)
            finally:
                if text.value: kernel.LocalFree(text)
                if descriptor.value: kernel.LocalFree(descriptor)
