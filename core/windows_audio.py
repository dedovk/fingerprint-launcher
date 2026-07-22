"""Small dependency-free wrapper around the Windows Core Audio endpoint API."""

from __future__ import annotations

import ctypes
import sys
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID


class WindowsAudioError(RuntimeError):
    pass


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(value: str) -> _GUID:
    return _GUID.from_buffer_copy(UUID(value).bytes_le)


def _com_method(pointer, index: int, restype, *argtypes):
    vtable = ctypes.cast(
        pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def _check_hresult(result: int, operation: str) -> None:
    if result < 0:
        unsigned = ctypes.c_uint32(result).value
        raise WindowsAudioError(f"{operation} failed: 0x{unsigned:08X}")


def _release(pointer: ctypes.c_void_p) -> None:
    if pointer.value:
        _com_method(pointer, 2, ctypes.c_ulong)(pointer)


class _EndpointVolume:
    def __init__(self, pointer: ctypes.c_void_p) -> None:
        self.pointer = pointer

    def get_volume(self) -> float:
        value = ctypes.c_float()
        result = _com_method(
            self.pointer, 9, ctypes.c_long, ctypes.POINTER(ctypes.c_float)
        )(self.pointer, ctypes.byref(value))
        _check_hresult(result, "GetMasterVolumeLevelScalar")
        return float(value.value)

    def set_volume(self, value: float) -> None:
        result = _com_method(
            self.pointer, 7, ctypes.c_long, ctypes.c_float, ctypes.c_void_p
        )(self.pointer, ctypes.c_float(value), None)
        _check_hresult(result, "SetMasterVolumeLevelScalar")

    def get_muted(self) -> bool:
        value = ctypes.c_int()
        result = _com_method(
            self.pointer, 15, ctypes.c_long, ctypes.POINTER(ctypes.c_int)
        )(self.pointer, ctypes.byref(value))
        _check_hresult(result, "GetMute")
        return bool(value.value)

    def set_muted(self, muted: bool) -> None:
        result = _com_method(
            self.pointer, 14, ctypes.c_long, ctypes.c_int, ctypes.c_void_p
        )(self.pointer, int(muted), None)
        _check_hresult(result, "SetMute")


@contextmanager
def _default_endpoint_volume() -> Iterator[_EndpointVolume]:
    if sys.platform != "win32":
        raise WindowsAudioError("Windows audio controls are only available on Windows")

    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long

    initialize_result = int(ole32.CoInitializeEx(None, 0x2))
    changed_mode = ctypes.c_long(0x80010106).value
    if initialize_result < 0 and initialize_result != changed_mode:
        _check_hresult(initialize_result, "CoInitializeEx")
    should_uninitialize = initialize_result in (0, 1)

    enumerator = ctypes.c_void_p()
    device = ctypes.c_void_p()
    endpoint = ctypes.c_void_p()
    try:
        clsid_enumerator = _guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
        iid_enumerator = _guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
        result = ole32.CoCreateInstance(
            ctypes.byref(clsid_enumerator),
            None,
            0x17,
            ctypes.byref(iid_enumerator),
            ctypes.byref(enumerator),
        )
        _check_hresult(result, "CoCreateInstance(IMMDeviceEnumerator)")

        result = _com_method(
            enumerator,
            4,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p),
        )(enumerator, 0, 1, ctypes.byref(device))
        _check_hresult(result, "GetDefaultAudioEndpoint")

        iid_endpoint_volume = _guid("5CDF2C82-841E-4546-9722-0CF74078229A")
        result = _com_method(
            device,
            3,
            ctypes.c_long,
            ctypes.POINTER(_GUID),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )(
            device,
            ctypes.byref(iid_endpoint_volume),
            0x17,
            None,
            ctypes.byref(endpoint),
        )
        _check_hresult(result, "IMMDevice.Activate(IAudioEndpointVolume)")
        yield _EndpointVolume(endpoint)
    finally:
        _release(endpoint)
        _release(device)
        _release(enumerator)
        if should_uninitialize:
            ole32.CoUninitialize()


def toggle_mute() -> bool:
    """Toggle the default playback device mute state and return the new state."""
    with _default_endpoint_volume() as endpoint:
        muted = not endpoint.get_muted()
        endpoint.set_muted(muted)
        return muted


def change_volume(delta_percent: int) -> int:
    """Change default playback volume relatively and return the resulting percent."""
    if isinstance(delta_percent, bool) or not isinstance(delta_percent, int):
        raise ValueError("delta_percent must be an integer")
    if not -100 <= delta_percent <= 100 or delta_percent == 0:
        raise ValueError("delta_percent must be between -100 and 100, excluding zero")

    with _default_endpoint_volume() as endpoint:
        scalar = min(1.0, max(0.0, endpoint.get_volume() + delta_percent / 100.0))
        endpoint.set_volume(scalar)
        return round(scalar * 100)
