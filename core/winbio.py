"""ctypes wrapper for Windows Biometric Framework fingerprint identify calls."""

from __future__ import annotations

import ctypes
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Iterable

import ctypes.wintypes as wt
from loguru import logger


WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_POOL_SYSTEM = 1
WINBIO_POOL_PRIVATE = 3
WINBIO_FLAG_DEFAULT = 0
WINBIO_ID_TYPE_NULL = 0
WINBIO_ID_TYPE_WILDCARD = 1
WINBIO_ID_TYPE_GUID = 2
WINBIO_ID_TYPE_SID = 3
WINBIO_STRING_LENGTH = 256
WINBIO_SENSOR_SUBTYPE_UNKNOWN = 0
WINBIO_FP_SENSOR_SUBTYPE_SWIPE = 1
WINBIO_FP_SENSOR_SUBTYPE_TOUCH = 2

S_OK = 0x00000000
WINBIO_E_UNSUPPORTED_FACTOR = 0x80098001
WINBIO_E_INVALID_UNIT = 0x80098002
WINBIO_E_UNKNOWN_ID = 0x80098003
WINBIO_E_CANCELED = 0x80098004
WINBIO_E_NO_MATCH = 0x80098005
WINBIO_E_CAPTURE_ABORTED = 0x80098006
WINBIO_E_ENROLLMENT_IN_PROGRESS = 0x80098007
WINBIO_E_BAD_CAPTURE = 0x80098008
WINBIO_E_INVALID_CONTROL_CODE = 0x80098009
WINBIO_E_DATA_COLLECTION_IN_PROGRESS = 0x8009800B
WINBIO_E_INVALID_DEVICE_STATE = 0x8009800F
WINBIO_E_DEVICE_BUSY = 0x80098010
WINBIO_E_SESSION_BUSY = 0x8009802D
WINBIO_E_SENSOR_UNAVAILABLE = 0x80098034
WINBIO_E_DEVICE_FAILURE = 0x80098036
WINBIO_I_MORE_DATA = 0x00090001
E_ACCESSDENIED = 0x80070005

TRANSIENT_IDENTIFY_HRESULTS = {
    WINBIO_E_CANCELED,
    WINBIO_E_CAPTURE_ABORTED,
    WINBIO_E_BAD_CAPTURE,
    WINBIO_E_DATA_COLLECTION_IN_PROGRESS,
    WINBIO_E_DEVICE_BUSY,
    WINBIO_E_SESSION_BUSY,
}

REJECT_DETAIL_MESSAGES = {
    1: "Палець занадто високо",
    2: "Палець занадто низько",
    3: "Палець занадто ліворуч",
    4: "Палець занадто праворуч",
    5: "Рух пальця занадто швидкий",
    6: "Рух пальця занадто повільний",
    7: "Низька якість зчитування",
    8: "Палець прикладено під завеликим кутом",
    9: "Контакт із сенсором занадто короткий",
    10: "Не вдалося об'єднати дані сканування",
}

FINGER_NAMES = {
    0x01: "Невідомий",
    0x02: "Великий правий",
    0x03: "Вказівний правий",
    0x04: "Середній правий",
    0x05: "Безіменний правий",
    0x06: "Мізинець правий",
    0x07: "Великий лівий",
    0x08: "Вказівний лівий",
    0x09: "Середній лівий",
    0x0A: "Безіменний лівий",
    0x0B: "Мізинець лівий",
    0xF5: "Невказаний палець 1",
    0xF6: "Невказаний палець 2",
    0xF7: "Невказаний палець 3",
    0xF8: "Невказаний палець 4",
    0xF9: "Невказаний палець 5",
    0xFA: "Невказаний палець 6",
    0xFB: "Невказаний палець 7",
    0xFC: "Невказаний палець 8",
    0xFD: "Невказаний палець 9",
    0xFE: "Невказаний палець 10",
}


class WinBioError(RuntimeError):
    """Raised when a WinBio operation fails before identify can return a result."""

    def __init__(self, hr: int, message: str):
        self.hr = normalize_hresult(hr)
        super().__init__(f"{message}: {format_hresult(self.hr)}")


class _AccountSid(ctypes.Structure):
    _fields_ = [
        ("Size", wt.ULONG),
        ("Data", ctypes.c_byte * 68),
    ]


class _IdentityValue(ctypes.Union):
    _fields_ = [
        ("Null", wt.ULONG),
        ("Wildcard", wt.ULONG),
        ("TemplateGuid", ctypes.c_byte * 16),
        ("AccountSid", _AccountSid),
    ]


class WINBIO_IDENTITY(ctypes.Structure):
    _fields_ = [
        ("Type", wt.ULONG),
        ("Value", _IdentityValue),
    ]


class WINBIO_VERSION(ctypes.Structure):
    _fields_ = [
        ("MajorVersion", wt.DWORD),
        ("MinorVersion", wt.DWORD),
    ]


class WINBIO_UNIT_SCHEMA(ctypes.Structure):
    _fields_ = [
        ("UnitId", wt.ULONG),
        ("PoolType", wt.ULONG),
        ("BiometricFactor", wt.ULONG),
        ("SensorSubType", wt.ULONG),
        ("Capabilities", wt.ULONG),
        ("DeviceInstanceId", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("Description", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("Manufacturer", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("Model", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("SerialNumber", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("FirmwareVersion", WINBIO_VERSION),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value: uuid.UUID | str) -> "GUID":
        parsed = value if isinstance(
            value, uuid.UUID) else uuid.UUID(str(value))
        data = parsed.bytes_le
        return cls(
            int.from_bytes(data[0:4], "little"),
            int.from_bytes(data[4:6], "little"),
            int.from_bytes(data[6:8], "little"),
            (ctypes.c_ubyte * 8).from_buffer_copy(data[8:16]),
        )

    def to_uuid(self) -> uuid.UUID:
        data = (
            int(self.Data1).to_bytes(4, "little")
            + int(self.Data2).to_bytes(2, "little")
            + int(self.Data3).to_bytes(2, "little")
            + bytes(self.Data4)
        )
        return uuid.UUID(bytes_le=data)


class WINBIO_STORAGE_SCHEMA(ctypes.Structure):
    _fields_ = [
        ("BiometricFactor", wt.ULONG),
        ("DatabaseId", GUID),
        ("DataFormat", GUID),
        ("Attributes", wt.ULONG),
        ("FilePath", wt.WCHAR * WINBIO_STRING_LENGTH),
        ("ConnectionString", wt.WCHAR * WINBIO_STRING_LENGTH),
    ]


@dataclass(frozen=True)
class IdentifyResult:
    hr: int
    unit_id: int
    guid: str
    sub_factor: int
    finger_name: str
    reject_detail: int
    identity_type: int = WINBIO_ID_TYPE_NULL
    identity_type_name: str = "NULL"
    sid: str = ""
    raw_identity: str = ""

    @property
    def identity_value(self) -> str:
        return self.guid or self.sid or self.raw_identity


@dataclass(frozen=True)
class BiometricUnit:
    unit_id: int
    pool_type: int
    biometric_factor: int
    sensor_subtype: int
    capabilities: int
    device_instance_id: str
    description: str
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str


@dataclass(frozen=True)
class BiometricDatabase:
    biometric_factor: int
    database_id: str
    data_format: str
    attributes: int
    file_path: str
    connection_string: str


@dataclass(frozen=True)
class ConsoleFocusResult:
    ok: bool
    console_hwnd: int
    foreground_hwnd: int
    message: str


def normalize_hresult(hr: int) -> int:
    """Return HRESULT as an unsigned 32-bit integer for stable comparisons."""

    return int(hr) & 0xFFFFFFFF


def format_hresult(hr: int) -> str:
    return f"0x{normalize_hresult(hr):08x}"


def hresult_message(hr: int) -> str:
    messages = {
        S_OK: "OK",
        WINBIO_E_UNSUPPORTED_FACTOR: "Біометричний фактор не підтримується",
        WINBIO_E_INVALID_UNIT: "Невірний ID біометричного пристрою",
        WINBIO_E_UNKNOWN_ID: "Відбиток не відповідає жодному відомому користувачу",
        WINBIO_E_CANCELED: "Біометричну операцію скасовано до завершення",
        WINBIO_E_NO_MATCH: "Палець не знайдено в Windows Hello",
        WINBIO_E_CAPTURE_ABORTED: "Зчитування відбитка було перервано",
        WINBIO_E_BAD_CAPTURE: "Погане зчитування відбитка",
        WINBIO_E_ENROLLMENT_IN_PROGRESS: "Триває реєстрація відбитка",
        WINBIO_E_INVALID_CONTROL_CODE: "Сенсор не підтримує цей control code",
        WINBIO_E_DATA_COLLECTION_IN_PROGRESS: "Інше зчитування вже виконується",
        WINBIO_E_INVALID_DEVICE_STATE: "Сенсор у неправильному стані для операції",
        WINBIO_E_DEVICE_BUSY: "Сенсор зайнятий",
        WINBIO_E_SESSION_BUSY: "Сесія вже виконує іншу операцію",
        WINBIO_E_SENSOR_UNAVAILABLE: "Сенсор недоступний",
        WINBIO_E_DEVICE_FAILURE: "Збій біометричного сенсора",
        WINBIO_I_MORE_DATA: "Потрібно більше даних",
        E_ACCESSDENIED: "Відмовлено в доступі",
    }
    return messages.get(normalize_hresult(hr), "Невідома помилка WinBio")


def is_transient_identify_error(hr: int) -> bool:
    return normalize_hresult(hr) in TRANSIENT_IDENTIFY_HRESULTS


def reject_detail_message(reject_detail: int) -> str:
    return REJECT_DETAIL_MESSAGES.get(int(reject_detail), "Деталі відхилення відсутні")


def identity_type_name(identity_type: int) -> str:
    names = {
        WINBIO_ID_TYPE_NULL: "NULL",
        WINBIO_ID_TYPE_WILDCARD: "WILDCARD",
        WINBIO_ID_TYPE_GUID: "GUID",
        WINBIO_ID_TYPE_SID: "SID",
    }
    return names.get(int(identity_type), f"UNKNOWN({identity_type})")


def identity_key(identity_type: int, identity_value: str, sub_factor: int) -> str:
    return f"{int(identity_type)}:{identity_value}:{int(sub_factor):02x}"


def sensor_subtype_name(sensor_subtype: int) -> str:
    names = {
        WINBIO_SENSOR_SUBTYPE_UNKNOWN: "unknown",
        WINBIO_FP_SENSOR_SUBTYPE_SWIPE: "swipe",
        WINBIO_FP_SENSOR_SUBTYPE_TOUCH: "touch",
    }
    return names.get(int(sensor_subtype), f"unknown({sensor_subtype})")


def _sid_bytes_to_string(sid_bytes: bytes) -> str:
    if not sid_bytes:
        return ""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(wt.LPWSTR)]
    advapi32.ConvertSidToStringSidW.restype = wt.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    sid_buffer = ctypes.create_string_buffer(sid_bytes)
    string_sid = wt.LPWSTR()
    ok = advapi32.ConvertSidToStringSidW(
        ctypes.cast(sid_buffer, ctypes.c_void_p),
        ctypes.byref(string_sid),
    )
    if not ok:
        return f"SID(raw:{sid_bytes.hex()})"

    try:
        return string_sid.value
    finally:
        kernel32.LocalFree(ctypes.cast(string_sid, ctypes.c_void_p))


def ensure_console_foreground() -> ConsoleFocusResult:
    """Give the current Win32 console foreground focus for WBF system-pool capture."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    kernel32.GetConsoleWindow.argtypes = []
    kernel32.GetConsoleWindow.restype = wt.HWND
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wt.HWND
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetForegroundWindow.restype = wt.BOOL

    console_hwnd = kernel32.GetConsoleWindow()
    if not console_hwnd:
        return ConsoleFocusResult(
            ok=False,
            console_hwnd=0,
            foreground_hwnd=int(user32.GetForegroundWindow() or 0),
            message=(
                "Win32 console window не знайдено. Git Bash/mintty часто запускає "
                "Python без справжнього console HWND; запусти тест із PowerShell, "
                "Windows Terminal або cmd.exe."
            ),
        )

    user32.SetForegroundWindow(console_hwnd)
    time.sleep(0.15)
    foreground_hwnd = user32.GetForegroundWindow()
    ok = foreground_hwnd == console_hwnd
    return ConsoleFocusResult(
        ok=ok,
        console_hwnd=int(console_hwnd),
        foreground_hwnd=int(foreground_hwnd or 0),
        message="Console window у foreground" if ok else "Не вдалося зробити console window foreground",
    )


def enumerate_biometric_units() -> list[BiometricUnit]:
    winbio = ctypes.WinDLL("winbio.dll")
    winbio.WinBioEnumBiometricUnits.argtypes = [
        wt.ULONG,
        ctypes.POINTER(ctypes.POINTER(WINBIO_UNIT_SCHEMA)),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    winbio.WinBioEnumBiometricUnits.restype = ctypes.c_long
    winbio.WinBioFree.argtypes = [ctypes.c_void_p]
    winbio.WinBioFree.restype = None

    schema_array = ctypes.POINTER(WINBIO_UNIT_SCHEMA)()
    count = ctypes.c_size_t()
    hr = normalize_hresult(
        winbio.WinBioEnumBiometricUnits(
            WINBIO_TYPE_FINGERPRINT,
            ctypes.byref(schema_array),
            ctypes.byref(count),
        )
    )
    if hr != S_OK:
        raise WinBioError(hr, "Не вдалося перелічити біометричні сенсори")

    units: list[BiometricUnit] = []
    try:
        for index in range(count.value):
            schema = schema_array[index]
            units.append(
                BiometricUnit(
                    unit_id=int(schema.UnitId),
                    pool_type=int(schema.PoolType),
                    biometric_factor=int(schema.BiometricFactor),
                    sensor_subtype=int(schema.SensorSubType),
                    capabilities=int(schema.Capabilities),
                    device_instance_id=str(
                        schema.DeviceInstanceId).rstrip("\x00"),
                    description=str(schema.Description).rstrip("\x00"),
                    manufacturer=str(schema.Manufacturer).rstrip("\x00"),
                    model=str(schema.Model).rstrip("\x00"),
                    serial_number=str(schema.SerialNumber).rstrip("\x00"),
                    firmware_version=(
                        f"{schema.FirmwareVersion.MajorVersion}."
                        f"{schema.FirmwareVersion.MinorVersion}"
                    ),
                )
            )
    finally:
        if schema_array:
            winbio.WinBioFree(schema_array)
    return units


def enumerate_biometric_databases() -> list[BiometricDatabase]:
    winbio = ctypes.WinDLL("winbio.dll")
    winbio.WinBioEnumDatabases.argtypes = [
        wt.ULONG,
        ctypes.POINTER(ctypes.POINTER(WINBIO_STORAGE_SCHEMA)),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    winbio.WinBioEnumDatabases.restype = ctypes.c_long
    winbio.WinBioFree.argtypes = [ctypes.c_void_p]
    winbio.WinBioFree.restype = None

    schema_array = ctypes.POINTER(WINBIO_STORAGE_SCHEMA)()
    count = ctypes.c_size_t()
    hr = normalize_hresult(
        winbio.WinBioEnumDatabases(
            WINBIO_TYPE_FINGERPRINT,
            ctypes.byref(schema_array),
            ctypes.byref(count),
        )
    )
    if hr != S_OK:
        raise WinBioError(hr, "Не вдалося перелічити біометричні бази")

    databases: list[BiometricDatabase] = []
    try:
        for index in range(count.value):
            schema = schema_array[index]
            databases.append(
                BiometricDatabase(
                    biometric_factor=int(schema.BiometricFactor),
                    database_id=str(schema.DatabaseId.to_uuid()),
                    data_format=str(schema.DataFormat.to_uuid()),
                    attributes=int(schema.Attributes),
                    file_path=str(schema.FilePath).rstrip("\x00"),
                    connection_string=str(
                        schema.ConnectionString).rstrip("\x00"),
                )
            )
    finally:
        if schema_array:
            winbio.WinBioFree(schema_array)
    return databases


class WinBioSession:
    """A blocking WinBio identify session with optional timeout cancellation."""

    def __init__(
        self,
        pool_type: int = WINBIO_POOL_SYSTEM,
        unit_ids: Iterable[int] | None = None,
        database_id: uuid.UUID | str | None = None,
    ) -> None:
        self.pool_type = pool_type
        self._winbio = ctypes.WinDLL("winbio.dll")
        self._configure_api()
        self._session = wt.HANDLE()
        self._closed = False
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="WinBioIdentify")

        selected_unit_ids = list(unit_ids or [])
        selected_database_id = database_id
        if pool_type == WINBIO_POOL_PRIVATE:
            if not selected_unit_ids:
                units = enumerate_biometric_units()
                if not units:
                    raise WinBioError(
                        WINBIO_E_INVALID_UNIT,
                        "Біометричний сенсор не знайдено",
                    )
                private_units = [
                    u for u in units if u.pool_type == WINBIO_POOL_PRIVATE]
                if not private_units:
                    raise WinBioError(
                        WINBIO_E_INVALID_UNIT,
                        "Приватний (private) біометричний пул не зареєстровано. "
                        "Сенсор доступний лише в системному (Windows Hello) пулі.",
                    )
                selected_unit_ids = [private_units[0].unit_id]
            if selected_database_id is None:
                databases = enumerate_biometric_databases()
                if not databases:
                    raise WinBioError(
                        WINBIO_E_INVALID_UNIT,
                        "Біометрична база WinBio не знайдена",
                    )
                selected_database_id = databases[0].database_id

        self._database_guid = GUID.from_uuid(
            selected_database_id) if selected_database_id else None

        unit_array = None
        unit_count = 0
        if selected_unit_ids:
            unit_count = len(selected_unit_ids)
            unit_array = (wt.ULONG * unit_count)(*selected_unit_ids)

        database_ptr = ctypes.byref(
            self._database_guid) if self._database_guid else None
        hr = self._winbio.WinBioOpenSession(
            WINBIO_TYPE_FINGERPRINT,
            pool_type,
            WINBIO_FLAG_DEFAULT,
            unit_array,
            unit_count,
            database_ptr,
            ctypes.byref(self._session),
        )
        hr = normalize_hresult(hr)
        if hr != S_OK:
            self._executor.shutdown(wait=False, cancel_futures=True)
            raise WinBioError(hr, "Не вдалося відкрити WinBio сесію")

    def _configure_api(self) -> None:
        self._winbio.WinBioOpenSession.argtypes = [
            wt.ULONG,
            wt.ULONG,
            wt.ULONG,
            ctypes.POINTER(wt.ULONG),
            ctypes.c_size_t,
            ctypes.POINTER(GUID),
            ctypes.POINTER(wt.HANDLE),
        ]
        self._winbio.WinBioOpenSession.restype = ctypes.c_long

        self._winbio.WinBioCloseSession.argtypes = [wt.HANDLE]
        self._winbio.WinBioCloseSession.restype = ctypes.c_long

        self._winbio.WinBioIdentify.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(wt.ULONG),
            ctypes.POINTER(WINBIO_IDENTITY),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(wt.ULONG),
        ]
        self._winbio.WinBioIdentify.restype = ctypes.c_long

        if hasattr(self._winbio, "WinBioCancel"):
            self._winbio.WinBioCancel.argtypes = [wt.HANDLE]
            self._winbio.WinBioCancel.restype = ctypes.c_long

    def identify(self, timeout_ms: int | None = None) -> IdentifyResult | None:
        """Wait for a fingerprint and return the identified template or None on timeout."""

        if self._closed:
            raise RuntimeError("WinBioSession is closed")

        timeout = None if timeout_ms is None else max(timeout_ms, 0) / 1000
        with self._lock:
            future = self._executor.submit(self._identify_blocking)
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                self.cancel()
                try:
                    result = future.result(timeout=2)
                except TimeoutError:
                    return None
                if result.hr == WINBIO_E_CANCELED:
                    return None
                return result

    def cancel(self) -> None:
        if not self._closed and hasattr(self._winbio, "WinBioCancel"):
            self._winbio.WinBioCancel(self._session)

    def _identify_blocking(self) -> IdentifyResult:
        unit_id = wt.ULONG()
        identity = WINBIO_IDENTITY()
        sub_factor = ctypes.c_ubyte()
        reject_detail = wt.ULONG()

        hr = self._winbio.WinBioIdentify(
            self._session,
            ctypes.byref(unit_id),
            ctypes.byref(identity),
            ctypes.byref(sub_factor),
            ctypes.byref(reject_detail),
        )
        hr = normalize_hresult(hr)

        guid_str = ""
        sid_str = ""
        raw_identity = ""
        if hr == S_OK and identity.Type == WINBIO_ID_TYPE_GUID:
            raw = bytes(identity.Value.TemplateGuid)
            guid_str = str(uuid.UUID(bytes_le=raw))
            raw_identity = raw.hex()
        elif hr == S_OK and identity.Type == WINBIO_ID_TYPE_SID:
            sid_size = int(identity.Value.AccountSid.Size)
            sid_bytes = bytes(
                int(value) & 0xFF for value in identity.Value.AccountSid.Data[:sid_size]
            )
            raw_identity = sid_bytes.hex()
            sid_str = _sid_bytes_to_string(sid_bytes)

        finger_code = int(sub_factor.value)
        return IdentifyResult(
            hr=hr,
            unit_id=int(unit_id.value),
            guid=guid_str,
            sub_factor=finger_code,
            finger_name=FINGER_NAMES.get(
                finger_code, f"Невідомий (0x{finger_code:02x})"),
            reject_detail=int(reject_detail.value),
            identity_type=int(identity.Type),
            identity_type_name=identity_type_name(identity.Type),
            sid=sid_str,
            raw_identity=raw_identity,
        )

    def close(self) -> None:
        if self._closed:
            return
        self.cancel()
        self._winbio.WinBioCloseSession(self._session)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._closed = True

    def __enter__(self) -> "WinBioSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def acquire_focus() -> None:
    """Acquire WBF sensor focus so this process can identify fingerprints
    even when its window is not in the foreground (WINBIO_POOL_SYSTEM).

    Must be balanced with a corresponding release_focus() call.
    Raises WinBioError if WinBioAcquireFocus is unavailable or fails.
    """
    winbio = ctypes.WinDLL("winbio.dll")
    if not hasattr(winbio, "WinBioAcquireFocus"):
        raise WinBioError(
            E_ACCESSDENIED, "WinBioAcquireFocus не підтримується на цій версії Windows")
    winbio.WinBioAcquireFocus.argtypes = []
    winbio.WinBioAcquireFocus.restype = ctypes.c_long
    hr = normalize_hresult(winbio.WinBioAcquireFocus())
    if hr != S_OK:
        raise WinBioError(hr, "WinBioAcquireFocus failed")


def release_focus() -> None:
    """Release the WBF sensor focus acquired by acquire_focus().

    Safe to call even if acquire_focus() was never called or failed.
    """
    try:
        winbio = ctypes.WinDLL("winbio.dll")
        if not hasattr(winbio, "WinBioReleaseFocus"):
            return
        winbio.WinBioReleaseFocus.argtypes = []
        winbio.WinBioReleaseFocus.restype = ctypes.c_long
        winbio.WinBioReleaseFocus()
    except Exception:
        pass


if __name__ == "__main__":
    with WinBioSession(WINBIO_POOL_SYSTEM) as session:
        print("Прикладіть палець до сканера...")
        result = session.identify(timeout_ms=15000)
        if result is None:
            print("Timeout: палець не зчитано")
        else:
            print(
                f"hr={format_hresult(result.hr)} guid={result.guid} "
                f"sub_factor={result.sub_factor} finger={result.finger_name}"
            )

