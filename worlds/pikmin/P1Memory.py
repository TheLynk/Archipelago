"""Access to the game RAM in Dolphin through dolphin_memory_engine.

On Windows, a read-only scan of Dolphin's memory is used to detect the
"Enable Emulated Memory Size Override" option, which is not supported.
"""
import os
import struct
import sys

import dolphin_memory_engine as _dme

MEM1_START = 0x80000000
GC_DISC_MAGIC = 0xC2339F3D
_BOOT_CODES = (0x0D15EA5E, 0xE5207C22)
_MIN_MEM1 = 0x01800000
_MAX_MEM1 = 0x04000000



class _WinBackend:
    """Read-only access to Dolphin memory on Windows (ctypes), used for detection only."""

    PROCESS_NAMES = ("Dolphin.exe", "DolphinQt2.exe", "DolphinWx.exe")

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.wt = wintypes
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class MBI(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p),
                        ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", wintypes.DWORD),
                        ("PartitionId", wintypes.WORD),
                        ("RegionSize", ctypes.c_size_t),
                        ("State", wintypes.DWORD),
                        ("Protect", wintypes.DWORD),
                        ("Type", wintypes.DWORD)]

        class PE32(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD),
                        ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_void_p),
                        ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD),
                        ("szExeFile", ctypes.c_wchar * 260)]

        self.MBI, self.PE32 = MBI, PE32
        k = self.k32
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PE32)]
        k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PE32)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.VirtualQueryEx.restype = ctypes.c_size_t
        k.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
        k.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

    def _find_pid(self):
        names = self.PROCESS_NAMES
        env = os.environ.get("DME_DOLPHIN_PROCESS_NAME")
        if env:
            names = (env, env + ".exe")
        snap = self.k32.CreateToolhelp32Snapshot(0x2, 0)
        if not snap or snap == self.wt.HANDLE(-1).value:
            return None
        try:
            entry = self.PE32()
            entry.dwSize = self.ct.sizeof(self.PE32)
            ok = self.k32.Process32FirstW(snap, self.ct.byref(entry))
            while ok:
                if entry.szExeFile in names:
                    return entry.th32ProcessID
                ok = self.k32.Process32NextW(snap, self.ct.byref(entry))
        finally:
            self.k32.CloseHandle(snap)
        return None

    def _raw_read(self, handle, address: int, size: int):
        buf = self.ct.create_string_buffer(size)
        n = self.ct.c_size_t(0)
        if not self.k32.ReadProcessMemory(handle, self.ct.c_void_p(address), buf, size, self.ct.byref(n)):
            return None
        return buf.raw[:n.value] if n.value == size else None

    def mem1_size(self):
        """Simulated MEM1 size of the running game, or None if no game RAM is found."""
        pid = self._find_pid()
        if pid is None:
            return None
        handle = self.k32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not handle:
            return None
        try:
            mbi = self.MBI()
            addr = 0
            while addr < 0x7FFFFFFFFFFF:
                if self.k32.VirtualQueryEx(handle, self.ct.c_void_p(addr), self.ct.byref(mbi),
                                           self.ct.sizeof(mbi)) != self.ct.sizeof(mbi):
                    break
                base = mbi.BaseAddress or 0
                region = mbi.RegionSize
                if (mbi.State == 0x1000 and mbi.Type == 0x40000
                        and _MIN_MEM1 <= region <= 2 * _MAX_MEM1):
                    head = self._raw_read(handle, base, 0x100)
                    if (head and struct.unpack_from(">I", head, 0x1C)[0] == GC_DISC_MAGIC
                            and struct.unpack_from(">I", head, 0x20)[0] in _BOOT_CODES):
                        return struct.unpack_from(">I", head, 0xF0)[0]
                addr = base + region
        finally:
            self.k32.CloseHandle(handle)
        return None


_win = None


def _win_backend():
    global _win
    if _win is None and sys.platform == "win32":
        try:
            _win = _WinBackend()
        except Exception:
            _win = False
    return _win or None


def _dme_header_ok() -> bool:
    try:
        head = _dme.read_bytes(MEM1_START + 0x1C, 8)
    except Exception:
        return False
    magic, boot = struct.unpack(">II", head)
    return magic == GC_DISC_MAGIC and boot in _BOOT_CODES


_override_detected = False


def _check_override() -> bool:
    win = _win_backend()
    if win is None:
        return False
    try:
        size = win.mem1_size()
    except Exception:
        return False
    return size is not None and size != _MIN_MEM1


def hook() -> None:
    global _override_detected
    try:
        _dme.hook()
    except Exception:
        pass
    if _dme.is_hooked() and _dme_header_ok():
        _override_detected = False
        return
    try:
        _dme.un_hook()
    except Exception:
        pass
    _override_detected = _check_override()


def un_hook() -> None:
    try:
        _dme.un_hook()
    except Exception:
        pass


def is_hooked() -> bool:
    return _dme.is_hooked()


def memory_override_detected() -> bool:
    """True if the last failed hook was caused by "Enable Emulated Memory Size Override"."""
    return _override_detected


def read_bytes(address: int, size: int) -> bytes:
    return _dme.read_bytes(address, size)


trace_writes = False
block_writes = False


def _trace(address: int, size: int) -> None:
    if trace_writes:
        import logging
        import traceback
        caller = traceback.extract_stack(limit=3)[0]
        state = "BLOCKED" if block_writes else "written"
        logging.getLogger("Client").info(
            f"[DEBUG WRITE] 0x{address:08X} ({size} bytes, {state}) from {caller.name}:{caller.lineno}")


def write_bytes(address: int, data: bytes) -> None:
    _trace(address, len(data))
    if block_writes:
        return
    return _dme.write_bytes(address, data)


def read_byte(address: int) -> int:
    return _dme.read_byte(address)


def write_byte(address: int, value: int) -> None:
    _trace(address, 1)
    if block_writes:
        return
    return _dme.write_byte(address, value)
