import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from core.database import Database
from ui.finger_wizard import FingerWizard
from ui.i18n import tr
from ui.main_window import MainWindow
from ui.theme import THEME


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_wizard_picker_and_registry_data_integrate_without_resizing(tmp_path):
    app = _app()
    with Database(tmp_path / "ui.sqlite3") as db:
        wizard = FingerWizard(db, lang="uk")
        wizard.stack.setCurrentIndex(1)
        wizard._sync_window_size()
        original_size = wizard.size()

        wizard.action_type.show_popup()
        app.processEvents()
        assert wizard.size() == original_size
        wizard.action_type.popup.hide()

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        wizard._add_action()

        assert wizard.actions[0]["command_type"] == "sleep"
        assert wizard.actions[0]["command_data"] == {
            "schema_version": 1,
            "delay_before": 0.0,
            "delay_after": 0.0,
        }


def test_data_free_action_uses_compact_layout_after_value_action(tmp_path):
    app = _app()
    with Database(tmp_path / "compact.sqlite3") as db:
        wizard = FingerWizard(db, lang="uk")
        wizard.stack.setCurrentIndex(1)
        wizard.action_type.setCurrentIndex(wizard.action_type.findData("open_url"))
        wizard.action_value.setText("https://example.com")
        wizard._add_action()
        assert wizard.height() == 643

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        app.processEvents()

        assert wizard.height() == 560


def test_edit_launch_app_keeps_file_picker_and_stable_controls_width(tmp_path):
    app = _app()
    with Database(tmp_path / "edit-launch-app.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.stack.setCurrentIndex(1)
        wizard.actions = [
            {
                "command_type": "launch_app",
                "command_data": {
                    "schema_version": 1,
                    "path": "C:/Windows/System32/calc.exe",
                    "args": "",
                    "delay_before": 0.0,
                    "delay_after": 0.0,
                },
            }
        ]

        wizard._edit_action(0)

        assert not wizard.browse.isHidden()
        assert wizard.browse.text() == "Choose file"
        assert wizard.add_action_btn.text() == "Update action"
        assert wizard.browse.width() + wizard.controls_row.spacing() + wizard.add_action_btn.width() == 476

        with patch(
            "ui.finger_wizard.QFileDialog.getOpenFileName",
            return_value=("C:/Program Files/App/app.exe", ""),
        ):
            wizard.browse.click()
        assert wizard.action_value.text() == "C:/Program Files/App/app.exe"
        wizard.deleteLater()
        app.processEvents()


def test_main_window_formats_registry_actions(tmp_path):
    app = _app()
    with Database(tmp_path / "main.sqlite3") as db:
        finger_id = db.save_finger("guid", 3, "Finger")
        db.save_command(finger_id, "open_url", {"url": "https://example.com"})
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.fingers_table.item(0, 2).text()
        assert window.fingers_table.item(0, 3).text() == "https://example.com"
        for index in range(12):
            window._append_activity(f"Action {index}")
        assert len(window._activity_entries) == 10
        assert window._activity_entries[0][1] == "Action 11"
        assert window._activity_entries[-1][1] == "Action 2"
        assert window.activity_log_card.minimumHeight() == 406
        assert window._theme_buttons[0].toolTip() == "Світла"
        window.lang = "en"
        window.retranslate()
        assert window._theme_buttons[0].toolTip() == "Light"
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_applies_and_switches_dark_theme(tmp_path):
    app = _app()
    with Database(tmp_path / "dark-main.sqlite3") as db:
        db.set_setting("theme", "dark")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "dark"
        assert THEME.key == "dark"
        assert window._theme_buttons[3].diameter() == 38
        assert "#243044" in window.styleSheet()

        window.change_theme_key("light")
        assert THEME.key == "light"
        assert db.get_setting("theme") == "light"
        assert "#F5F5F7" in window.styleSheet()

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_applies_onyx_theme_and_wizard_controls(tmp_path):
    app = _app()
    with Database(tmp_path / "onyx-main.sqlite3") as db:
        db.set_setting("theme", "onyx")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "onyx"
        assert THEME.key == "onyx"
        assert window._theme_buttons[1].diameter() == 38
        assert "#1A1A1D" in window.styleSheet()
        assert THEME.settings_surface == "#1E1E22"
        assert window.autostart_mode_combo.property("role") == "settingsInput"
        assert window.activity_log_card.property("role") == "statusLog"
        assert window._theme_buttons[0]._outline_color().name() == "#111113"
        assert window._theme_buttons[1]._outline_color().name() == THEME.primary.lower()
        assert window._theme_buttons[2]._outline_color() is None

        wizard = FingerWizard(db, window, lang="en")
        wizard.stack.setCurrentIndex(1)
        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        wizard._add_action()
        action_row = wizard.actions_layout.itemAt(0).widget()
        action_buttons = action_row.findChildren(type(wizard.add_action_btn))
        assert {button.property("kind") for button in action_buttons} == {"actionSecondary"}
        wizard.stack.setCurrentIndex(0)
        wizard.scanned = False
        wizard._sync_nav()
        assert wizard.next_btn.property("iconName") == "inactive_next"

        wizard.deleteLater()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_language_change_retranslates_dynamic_text_and_fits_buttons(tmp_path):
    app = _app()
    with Database(tmp_path / "translations.sqlite3") as db:
        db.set_setting("language", "fr")
        db.set_setting("theme", "dark")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.support_text.text().startswith("Si l’application")
        assert window.monitor_status.text().startswith("En attente")
        window._show_update_status("update_no_releases", 100_000)
        assert window.update_status.text() == "Aucune version n’est encore publiée sur GitHub."

        window.lang = "es"
        window.copy_status.setText("Copied")
        window.retranslate()
        assert window.support_text.text().startswith("Si la aplicación")
        assert window.monitor_status.text().startswith("Esperando")
        assert window.update_status.text() == "Todavía no hay versiones publicadas en GitHub."
        assert window.copy_status.text() == "Copiado"

        window.lang = "ru"
        window.retranslate()
        window._activity_entries.clear()
        window.on_scan_action_result({
            "command_type": "open_url",
            "status": "success",
            "message": "https://example.com",
        })
        assert window._activity_entries[0][1].startswith("Выполнено:")
        for button in (
            window.add_btn,
            window.edit_btn,
            window.delete_btn,
            window.activation_hotkey_save,
            window.check_updates_btn,
            window.copy_trc20_btn,
        ):
            assert button.width() >= button.sizeHint().width()

        window.show()
        app.processEvents()
        assert 0 < window.stack.y() < window.tab_bar.height()
        assert window.tab_bar.height() - window.stack.y() == window.tabbed_content.OVERLAP

        window.scan_prompt.progress.setValue(400)
        window.scan_prompt.set_result("success")
        assert window.scan_prompt.progress.value() == 400
        short_prompt_height = window.scan_prompt.height()
        window.scan_prompt.set_result(tr("ru", "unknown_hello"))
        assert window.scan_prompt.message.height() > 40
        assert window.scan_prompt.height() > short_prompt_height
        window.scan_prompt.set_result("timeout", complete=True)
        assert window.scan_prompt.progress.value() == window.scan_prompt.PROGRESS_MAX

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_done_step_keeps_icon_title_and_message_separate(tmp_path):
    app = _app()
    with Database(tmp_path / "done-layout.sqlite3") as db:
        wizard = FingerWizard(db, lang="ru")
        wizard.stack.setCurrentIndex(2)
        wizard.done_label.setText(
            "Для пальца <b>Неуказанный палец 2</b> назначено действие: "
            "<span style='color:#1D74F7'>Заблокировать экран</span>"
        )
        wizard.show()
        app.processEvents()

        assert wizard.done_card.height() == 208
        assert wizard.done_icon.geometry().bottom() < wizard.done_title.geometry().top()
        assert wizard.done_title.geometry().bottom() < wizard.done_label.geometry().top()

        wizard.deleteLater()
        app.processEvents()


def test_failed_capture_keeps_scan_icon_size(tmp_path):
    app = _app()
    with Database(tmp_path / "capture-icon.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.show()
        app.processEvents()

        original_size = wizard.capture_icon.size()
        original_pixmap_size = wizard.capture_icon.pixmap().size()
        wizard._on_capture_failed(
            "unknown_finger",
            "This finger is not enrolled in Windows Hello. Open Windows Settings, "
            "add this finger, then return here.",
        )
        app.processEvents()

        assert wizard.capture_icon.size() == original_size
        assert wizard.capture_icon.size().width() == 72
        assert wizard.capture_icon.size().height() == 72
        assert wizard.capture_icon.pixmap().size() == original_pixmap_size

        wizard.deleteLater()
        app.processEvents()
