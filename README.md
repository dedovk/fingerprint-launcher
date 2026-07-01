# FingerprintLauncher Version 1.0.0

FingerprintLauncher is a Windows desktop app that runs user-defined actions
after a Windows Hello fingerprint scan.

The app stays in the tray, waits for an activation hotkey, asks for a finger
scan, identifies the finger through the Windows Biometric Framework, and runs
the actions assigned to matching finger profiles.

## Features

- Launch an application or file.
- Open a website in the default browser.
- Send a keyboard shortcut.
- Run a hidden PowerShell command.
- Lock the Windows session.
- Add multiple actions to one profile.
- Create multiple profiles for the same physical finger.
- Enable or disable saved actions from the main table.
- Start with Windows through the current user's `Run` registry key.
- Use light, dark, or gray themes.
- Switch the UI language between Ukrainian, English, Russian, French, and
  Spanish.

## Requirements

- Windows 10 or Windows 11.
- A Windows Hello compatible fingerprint sensor.
- At least one fingerprint enrolled in Windows Hello.
- Python 3.11, 3.12, or 3.13 for source runs.

Packaged builds do not require Python on the target machine. Fingerprint
matching is always handled by Windows; the app does not store fingerprint
templates.

## How It Works

1. Press the activation hotkey. The default is `ctrl+alt+f`.
2. Scan a Windows Hello enrolled finger.
3. `core/winbio.py` calls `WinBioIdentify`.
4. `core/database.py` finds enabled commands for matching profiles.
5. `core/executor.py` runs each command.

If the same physical finger has several profiles, enabled commands from all
matching profiles can run for that scan.

The SQLite database stores only WinBio identity data, the finger sub-factor,
profile labels, command definitions, and UI settings.

## Install From Source

```powershell
git clone https://github.com/dedovk/fingerprint-launcher.git
cd fingerprint-launcher
python -m pip install -e .
```

For development and tests:

```powershell
python -m pip install -e ".[dev]"
```

Run the app:

```powershell
python main.py
```

or, after editable installation:

```powershell
fingerprint-launcher-gui
```

## First Run

1. Confirm that the sensor works in Windows Hello.
2. Start FingerprintLauncher.
3. Open **My fingers**.
4. Click **Add**.
5. Scan a finger.
6. Name the profile.
7. Add one or more actions.
8. Save the profile.
9. Press the activation hotkey and scan the finger to run the actions.

The app is designed to run as a normal user process. It does not need
administrator rights.

## Supported Actions

| Action | Stored data |
| --- | --- |
| Launch application or file | `{"path": "C:\\Path\\App.exe", "args": ""}` |
| Open website | `{"url": "https://example.com"}` |
| Send hotkey | `{"keys": "ctrl+shift+t"}` |
| Run PowerShell command | `{"cmd": "Start-Process notepad", "hidden": true}` |
| Lock screen | `{}` |

Hotkeys are sent through the `keyboard` package. Windows-key aliases such as
`win`, `meta`, `cmd`, and `super` are normalized to `windows`.

## Autostart

Autostart is controlled from **Settings -> Startup**.

When enabled, FingerprintLauncher writes a per-user startup value:

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  FingerprintLauncher = "C:\Path\To\FingerprintLauncher.exe"
```

When disabled, that value is removed. The app also removes the legacy scheduled
task name `FingerprintLauncher` if it exists.

## Data Location

The database is stored in the current user's local app data folder:

```text
%LOCALAPPDATA%\FingerprintLauncher\fingerprints.sqlite3
```

Main tables:

- `fingers`: WinBio identity, sub-factor, profile label, timestamps.
- `commands`: action type, JSON payload, enabled flag.
- `settings`: UI, language, theme, hotkey, and startup settings.

## Project Layout

```text
core/
  database.py       SQLite persistence
  executor.py       Action execution
  winbio.py         Windows Biometric Framework bindings
services/
  autostart.py      Per-user Windows startup registration
ui/
  main_window.py    Main window and settings
  finger_wizard.py  Finger profile and action editor
  triggered_scan.py Hotkey-triggered scan worker
  scan_prompt.py    Scan prompt popup
  tray.py           System tray integration
tests/
  test_autostart.py
  test_database.py
  test_executor.py
  test_winbio.py
```

## Build

Install build dependencies:

```powershell
python -m pip install -e ".[build]"
```

Build the standalone Nuitka distribution:

```powershell
python build.py
```

## Installer

The repository includes Inno Setup scripts in `installer/`. The minimal script
is:

```powershell
ISCC.exe installer\setup.iss
```

The installer copies `dist\main.dist\*` into the install directory and can
launch the app after installation.

## Diagnostics

Check Windows Biometric Framework access:

```powershell
python check_wbf.py
```

Run tests:

```powershell
python -m pytest
```

The tests cover database behavior, command dispatch, WinBio helpers, and
autostart registry behavior.

## Notes

- Fingerprint templates remain inside Windows Hello.
- Finger capture and triggered scans run on worker threads.
- Closing the main window hides it; use the tray menu to quit.
- Some Windows-reserved hotkeys cannot be captured automatically, but can be
  typed manually in settings.

## License

Proprietary.

## Author

Diedov Kyrylo
