from __future__ import annotations

import argparse
import time

from core.winbio import (
    S_OK,
    WINBIO_E_NO_MATCH,
    WINBIO_E_UNKNOWN_ID,
    WINBIO_POOL_SYSTEM,
    WinBioSession,
    ensure_console_foreground,
    enumerate_biometric_units,
    format_hresult,
    hresult_message,
    identity_key,
    is_transient_identify_error,
    reject_detail_message,
    sensor_subtype_name,
)


OVERALL_TIMEOUT_SECONDS = 30
ATTEMPT_TIMEOUT_MS = OVERALL_TIMEOUT_SECONDS * 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Console smoke test for Windows Biometric Framework identification"
    )
    parser.add_argument(
        "--blocking",
        action="store_true",
        help="wait without calling WinBioCancel; stop with Ctrl+C",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="print WBF sensor and console-focus diagnostics",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.diagnose:
        print_diagnostics()

    if args.blocking:
        focus = ensure_console_foreground()
        print(
            f"Focus: {focus.message} "
            f"(console=0x{focus.console_hwnd:x}, foreground=0x{focus.foreground_hwnd:x})"
        )
        print("Blocking mode: touch the fingerprint sensor. Press Ctrl+C to stop.")
        with WinBioSession(WINBIO_POOL_SYSTEM) as session:
            result = session.identify(timeout_ms=None)
        return print_result(result)

    focus = ensure_console_foreground()
    print(
        f"Focus: {focus.message} "
        f"(console=0x{focus.console_hwnd:x}, foreground=0x{focus.foreground_hwnd:x})"
    )
    if not focus.ok:
        print(
            "Warning: without a foreground Win32 window, the WBF system pool "
            "may not start capture."
        )

    deadline = time.monotonic() + OVERALL_TIMEOUT_SECONDS
    attempt = 1
    last_result = None

    print(f"Touch the fingerprint sensor within {OVERALL_TIMEOUT_SECONDS} seconds...")
    while time.monotonic() < deadline:
        with WinBioSession(WINBIO_POOL_SYSTEM) as session:
            result = session.identify(timeout_ms=ATTEMPT_TIMEOUT_MS)

        if result is None:
            print("Timeout: WinBioIdentify did not return a result within the allotted time")
            attempt += 1
            break

        last_result = result
        if result.hr == S_OK:
            break

        message = hresult_message(result.hr)
        detail = reject_detail_message(result.reject_detail)
        print(
            f"Attempt {attempt}: {format_hresult(result.hr)} ({message}); "
            f"reject_detail={result.reject_detail} ({detail})"
        )

        if result.hr in (WINBIO_E_UNKNOWN_ID, WINBIO_E_NO_MATCH):
            break

        if is_transient_identify_error(result.hr):
            print("Transient driver or sensor error detected; retrying capture...")
            time.sleep(0.35)
            attempt += 1
            continue

        break

    result = last_result
    if result is None:
        print("Timeout: no finger was read")
        return 1

    return print_result(result)


def print_result(result) -> int:
    print(f"HRESULT: {format_hresult(result.hr)} ({hresult_message(result.hr)})")
    print(f"Unit ID: {result.unit_id}")
    print(f"Identity type: {result.identity_type} ({result.identity_type_name})")
    print(f"GUID: {result.guid or '<none>'}")
    print(f"SID: {result.sid or '<none>'}")
    print(f"Raw identity: {result.raw_identity or '<none>'}")
    print(f"Binding key: {identity_key(result.identity_type, result.identity_value, result.sub_factor)}")
    print(f"Sub factor: {result.sub_factor:#04x}")
    print(f"Finger: {result.finger_name}")
    print(f"Reject detail: {result.reject_detail} ({reject_detail_message(result.reject_detail)})")
    return 0 if result.hr == S_OK else 2


def print_diagnostics() -> None:
    focus = ensure_console_foreground()
    print("=== Console focus ===")
    print(f"OK: {focus.ok}")
    print(f"Console HWND: 0x{focus.console_hwnd:x}")
    print(f"Foreground HWND: 0x{focus.foreground_hwnd:x}")
    print(f"Message: {focus.message}")
    print()

    print("=== WBF biometric units ===")
    units = enumerate_biometric_units()
    if not units:
        print("No biometric sensors were found by WinBioEnumBiometricUnits")
        return

    for unit in units:
        print(f"Unit ID: {unit.unit_id}")
        print(f"  Pool type: {unit.pool_type}")
        print(f"  Factor: 0x{unit.biometric_factor:08x}")
        print(f"  Sensor subtype: {unit.sensor_subtype} ({sensor_subtype_name(unit.sensor_subtype)})")
        print(f"  Capabilities: 0x{unit.capabilities:08x}")
        print(f"  Device: {unit.device_instance_id}")
        print(f"  Description: {unit.description}")
        print(f"  Manufacturer: {unit.manufacturer}")
        print(f"  Model: {unit.model}")
        print(f"  Firmware: {unit.firmware_version}")


if __name__ == "__main__":
    raise SystemExit(main())
