from types import SimpleNamespace

from core.winbio import S_OK, WINBIO_E_BAD_CAPTURE
from ui.i18n import (
    BIOMETRIC_TRANSLATIONS,
    LANGUAGES,
    localized_finger_name,
    localized_winbio_message,
    tr,
)
from ui.triggered_scan import TriggeredFingerprintScan


def test_biometric_messages_exist_for_every_supported_language():
    assert set(BIOMETRIC_TRANSLATIONS) == set(LANGUAGES)
    expected_keys = set(BIOMETRIC_TRANSLATIONS["en"])
    assert expected_keys
    for language in LANGUAGES:
        assert set(BIOMETRIC_TRANSLATIONS[language]) == expected_keys


def test_winbio_status_uses_selected_language():
    assert localized_winbio_message("en", WINBIO_E_BAD_CAPTURE) == "Poor fingerprint capture"
    assert localized_winbio_message("uk", WINBIO_E_BAD_CAPTURE) == "Погане зчитування відбитка"


def test_system_finger_name_uses_selected_language():
    assert localized_finger_name("en", 0xF9) == "Unspecified finger 5"
    assert localized_finger_name("uk", 0xF9) == "Невказаний палець 5"
    assert localized_finger_name("fr", 0x03) == "Index droit"


def test_triggered_scan_does_not_emit_low_level_ukrainian_message(tmp_path):
    worker = TriggeredFingerprintScan(tmp_path / "status.sqlite3", lang="en")
    errors = []
    worker.error.connect(errors.append)

    worker._handle_result(None, SimpleNamespace(hr=WINBIO_E_BAD_CAPTURE))

    assert errors == ["Poor fingerprint capture"]


def test_dynamic_settings_messages_are_translated_for_every_language():
    keys = {
        "hotkey_status",
        "checking_updates",
        "update_no_releases",
        "update_up_to_date",
        "update_available",
        "update_check_failed",
        "support_text",
        "copy",
        "copied",
        "executed",
        "settings_menu",
        "scan_popup_waiting",
        "timeout",
    }

    for language in set(LANGUAGES) - {"en"}:
        for key in keys:
            assert tr(language, key) != tr("en", key), (language, key)


def test_tray_settings_label_has_no_ellipsis_in_any_language():
    for language in LANGUAGES:
        assert "..." not in tr(language, "settings_menu")
        assert "…" not in tr(language, "settings_menu")


def test_triggered_scan_localizes_system_finger_name(tmp_path):
    class EmptyDatabase:
        def update_guid(self, *_args):
            pass

        def get_commands(self, *_args):
            return []

    worker = TriggeredFingerprintScan(tmp_path / "finger-name.sqlite3", lang="en")
    errors = []
    worker.error.connect(errors.append)
    result = SimpleNamespace(
        hr=S_OK,
        guid="guid",
        identity_value="guid",
        identity_type=2,
        sub_factor=0xF9,
    )

    worker._handle_result(EmptyDatabase(), result)

    assert len(errors) == 1
    assert "Unspecified finger 5" in errors[0]
    assert "Невказаний" not in errors[0]
