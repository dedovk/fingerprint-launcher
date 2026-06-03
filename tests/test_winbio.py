import threading
from concurrent.futures import TimeoutError

from core.winbio import (
    IdentifyResult,
    WINBIO_E_BAD_CAPTURE,
    WINBIO_E_CANCELED,
    WINBIO_ID_TYPE_GUID,
    WINBIO_ID_TYPE_SID,
    WinBioSession,
    hresult_message,
    identity_key,
    identity_type_name,
    is_transient_identify_error,
    normalize_hresult,
    reject_detail_message,
)


def test_hresult_constants_match_winbio_err_header():
    assert WINBIO_E_CANCELED == 0x80098004
    assert WINBIO_E_BAD_CAPTURE == 0x80098008


def test_signed_hresult_normalizes_to_unsigned():
    assert normalize_hresult(-2146861052) == WINBIO_E_CANCELED


def test_transient_hresult_has_human_message():
    assert is_transient_identify_error(WINBIO_E_CANCELED)
    assert "скасовано" in hresult_message(WINBIO_E_CANCELED)


def test_reject_detail_message():
    assert reject_detail_message(5) == "Рух пальця занадто швидкий"


def test_identity_type_constants_match_observed_wbf_values():
    assert WINBIO_ID_TYPE_GUID == 2
    assert WINBIO_ID_TYPE_SID == 3
    assert identity_type_name(WINBIO_ID_TYPE_SID) == "SID"
    assert identity_key(WINBIO_ID_TYPE_SID, "S-1-5-21-x", 0xF6) == "3:S-1-5-21-x:f6"


def test_identify_returns_none_when_our_timeout_cancels_operation():
    class FakeFuture:
        def __init__(self):
            self.calls = 0

        def result(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError()
            return IdentifyResult(WINBIO_E_CANCELED, 0, "", 0, "Невідомий", 0)

    class FakeExecutor:
        def __init__(self):
            self.future = FakeFuture()

        def submit(self, fn):
            return self.future

    session = object.__new__(WinBioSession)
    session._closed = False
    session._lock = threading.Lock()
    session._executor = FakeExecutor()
    session.cancel = lambda: None

    assert session.identify(timeout_ms=1) is None
