"""Acces a la RAM du jeu dans Dolphin (#58).

Facade compatible avec `dolphin_memory_engine` (hook, un_hook, is_hooked,
read_bytes, write_bytes, read_byte, write_byte).

Le module `dolphin_memory_engine` (binding Python, v1.3.x) ne trouve la RAM
emulee que si MEM1 fait sa taille d'origine : avec l'option Dolphin "Enable
Emulated Memory Size Override" (exigee par l'apworld Pikmin 2, MEM1 = 64 Mo),
le hook echoue et le client ne detecte jamais le jeu. On essaie donc toujours
dolphin_memory_engine en premier (comportement inchange) et, sous Windows, on
retombe sur un acces direct (ReadProcessMemory / WriteProcessMemory) qui
repere MEM1 quelle que soit sa taille, comme le fait le Dolphin Memory Engine
recent : region memoire partagee de Dolphin dont l'en-tete contient le "magic
word" des disques GameCube (0xC2339F3D a 0x8000001C).
"""
import os
import struct
import sys

import dolphin_memory_engine as _dme

MEM1_START = 0x80000000
GC_DISC_MAGIC = 0xC2339F3D
_BOOT_CODES = (0x0D15EA5E, 0xE5207C22)  # boot normal / JTAG (0x80000020)
_MIN_MEM1 = 0x01800000   # 24 Mo (taille d'origine)
_MAX_MEM1 = 0x04000000   # 64 Mo (maximum de l'option Dolphin)

_backend = None  # None, "dme" ou "win"


class _WinBackend:
    """Acces direct a la memoire de Dolphin sous Windows (ctypes)."""

    PROCESS_NAMES = ("Dolphin.exe", "DolphinQt2.exe", "DolphinWx.exe")

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.wt = wintypes
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handle = None
        self.base = 0
        self.size = 0

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
        k.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]

    # -- processus ---------------------------------------------------------
    def _find_pid(self):
        names = self.PROCESS_NAMES
        env = os.environ.get("DME_DOLPHIN_PROCESS_NAME")
        if env:
            names = (env, env + ".exe")
        snap = self.k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
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

    def _raw_read(self, address: int, size: int):
        buf = self.ct.create_string_buffer(size)
        n = self.ct.c_size_t(0)
        if not self.k32.ReadProcessMemory(self.handle, self.ct.c_void_p(address), buf, size, self.ct.byref(n)):
            return None
        return buf.raw[:n.value] if n.value == size else None

    def hook(self) -> bool:
        self.un_hook()
        pid = self._find_pid()
        if pid is None:
            return False
        # QUERY_INFORMATION | VM_OPERATION | VM_READ | VM_WRITE
        self.handle = self.k32.OpenProcess(0x0400 | 0x0008 | 0x0010 | 0x0020, False, pid)
        if not self.handle:
            self.handle = None
            return False
        mbi = self.MBI()
        addr = 0
        while addr < 0x7FFFFFFFFFFF:
            if self.k32.VirtualQueryEx(self.handle, self.ct.c_void_p(addr), self.ct.byref(mbi),
                                       self.ct.sizeof(mbi)) != self.ct.sizeof(mbi):
                break
            base = mbi.BaseAddress or 0
            region = mbi.RegionSize
            # MEM_COMMIT (0x1000) + MEM_MAPPED (0x40000) : vue de la memoire partagee.
            if (mbi.State == 0x1000 and mbi.Type == 0x40000
                    and _MIN_MEM1 <= region <= 2 * _MAX_MEM1):
                head = self._raw_read(base, 0x100)
                if (head and struct.unpack_from(">I", head, 0x1C)[0] == GC_DISC_MAGIC
                        and struct.unpack_from(">I", head, 0x20)[0] in _BOOT_CODES):
                    # Taille de MEM1 simulee (OS globals, 0x800000F0).
                    size = struct.unpack_from(">I", head, 0xF0)[0]
                    if not (_MIN_MEM1 <= size <= _MAX_MEM1):
                        size = min(region, _MAX_MEM1)
                    self.base, self.size = base, min(size, region)
                    return True
            addr = base + region
        self.un_hook()
        return False

    def un_hook(self) -> None:
        if self.handle:
            try:
                self.k32.CloseHandle(self.handle)
            except Exception:
                pass
        self.handle, self.base, self.size = None, 0, 0

    def is_hooked(self) -> bool:
        if not self.handle:
            return False
        code = self.wt.DWORD(0)
        if not self.k32.GetExitCodeProcess(self.handle, self.ct.byref(code)) or code.value != 259:
            self.un_hook()  # STILL_ACTIVE = 259
            return False
        return True

    def _offset(self, address: int, size: int) -> int:
        off = address - MEM1_START
        if not self.handle or off < 0 or off + size > self.size:
            raise RuntimeError(f"Address 0x{address:08X} out of emulated RAM")
        return off

    def read_bytes(self, address: int, size: int) -> bytes:
        data = self._raw_read(self.base + self._offset(address, size), size)
        if data is None:
            raise RuntimeError(f"Could not read 0x{address:08X}")
        return data

    def write_bytes(self, address: int, data: bytes) -> None:
        off = self._offset(address, len(data))
        n = self.ct.c_size_t(0)
        if not self.k32.WriteProcessMemory(self.handle, self.ct.c_void_p(self.base + off),
                                           data, len(data), self.ct.byref(n)) or n.value != len(data):
            raise RuntimeError(f"Could not write 0x{address:08X}")


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
    """Verifie que dolphin_memory_engine lit bien la RAM d'un jeu GameCube.

    Avec une MEM1 agrandie, il peut se "hooker" sur une mauvaise region
    memoire de Dolphin : on lirait alors n'importe quoi (d'ou "Wrong Game")."""
    try:
        head = _dme.read_bytes(MEM1_START + 0x1C, 8)
    except Exception:
        return False
    magic, boot = struct.unpack(">II", head)
    return magic == GC_DISC_MAGIC and boot in _BOOT_CODES


def hook() -> None:
    global _backend
    try:
        _dme.hook()
    except Exception:
        pass
    if _dme.is_hooked():
        if _dme_header_ok():
            _backend = "dme"
            return
        try:
            _dme.un_hook()  # mauvaise region : on passe a l'acces direct
        except Exception:
            pass
    win = _win_backend()
    _backend = "win" if win is not None and win.hook() else None


def un_hook() -> None:
    global _backend
    if _backend == "win" and _win:
        _win.un_hook()
    else:
        try:
            _dme.un_hook()
        except Exception:
            pass
    _backend = None


def is_hooked() -> bool:
    if _backend == "win":
        return bool(_win) and _win.is_hooked()
    return _dme.is_hooked()


def uses_direct_access() -> bool:
    """Vrai si l'acces direct Windows est utilise (MEM1 agrandie)."""
    return _backend == "win"


def read_bytes(address: int, size: int) -> bytes:
    if _backend == "win":
        return _win.read_bytes(address, size)
    return _dme.read_bytes(address, size)


def write_bytes(address: int, data: bytes) -> None:
    if _backend == "win":
        return _win.write_bytes(address, data)
    return _dme.write_bytes(address, data)


def read_byte(address: int) -> int:
    if _backend == "win":
        return _win.read_bytes(address, 1)[0]
    return _dme.read_byte(address)


def write_byte(address: int, value: int) -> None:
    if _backend == "win":
        return _win.write_bytes(address, bytes([value & 0xFF]))
    return _dme.write_byte(address, value)
