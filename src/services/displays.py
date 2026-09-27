"""Locate the connected virtual monitor without falling back to a real display."""
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import sys


@dataclass(frozen=True)
class Display:
    name: str
    description: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    @property
    def is_virtual(self) -> bool:
        return any(word in self.description.casefold() for word in ("virtual", "indirect", "iddsample"))

    def contains(self, bounds: dict) -> bool:
        return (bounds["left"] >= self.x and bounds["top"] >= self.y
                and bounds["left"] + bounds["width"] <= self.x + self.width
                and bounds["top"] + bounds["height"] <= self.y + self.height)


def list_displays() -> list[Display]:
    if sys.platform != "win32":
        raise RuntimeError("가상 디스플레이 다운로드는 Windows에서 지원됩니다.")

    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                         ctypes.POINTER(DISPLAY_DEVICE), wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFOEX)]
    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                         callback_type, wintypes.LPARAM]
    descriptions = {}
    index = 0
    while True:
        device = DISPLAY_DEVICE()
        device.cb = ctypes.sizeof(device)
        if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        descriptions[device.DeviceName] = device.DeviceString
        index += 1
    displays = []

    @callback_type
    def collect(handle, _dc, _rect, _data):
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            rect = info.rcMonitor
            displays.append(Display(info.szDevice, descriptions.get(info.szDevice, ""),
                                    rect.left, rect.top, rect.right - rect.left,
                                    rect.bottom - rect.top, bool(info.dwFlags & 1)))
        return True

    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return displays


def choose_virtual_display(displays: list[Display]) -> Display:
    candidates = [d for d in displays if d.is_virtual and not d.primary]
    if len(displays) < 3 or len(candidates) != 1:
        raise RuntimeError("두 메인 화면 외에 가상 디스플레이 하나가 연결되어 있어야 합니다. 디스플레이 설정을 확인하세요.")
    display = candidates[0]
    if display.width < 640 or display.height < 480:
        raise RuntimeError("가상 디스플레이 해상도를 640×480 이상으로 설정하세요.")
    return display


def get_virtual_display() -> Display:
    return choose_virtual_display(list_displays())


def ensure_display_connected(expected: Display) -> None:
    if expected not in list_displays():
        raise RuntimeError("가상 디스플레이 연결 또는 위치가 바뀌어 다운로드를 중단했습니다.")
