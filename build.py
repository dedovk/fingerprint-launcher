from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BASE_CMD = [
    sys.executable,
    "-m",
    "nuitka",
    "--standalone",
    # "--onefile",
    "--assume-yes-for-downloads",
    "--windows-icon-from-ico=assets/icon.ico",
    "--company-name=dedovk",
    "--product-name=FingerprintLauncher",
    "--file-version=1.0.0.0",
    "--product-version=1.0.0.0",
    "--enable-plugin=pyqt6",
    "--include-data-dir=assets=assets",
    "--output-dir=dist",
]


def build(entry: str, output_name: str, extra_args: list[str] | None = None) -> None:
    cache_dir = Path(".nuitka-cache").resolve()
    cache_dir.mkdir(exist_ok=True)
    env = dict(os.environ, NUITKA_CACHE_DIR=str(cache_dir))
    subprocess.check_call(
        [
            *BASE_CMD,
            *(extra_args or []),
            f"--output-filename={output_name}",
            entry,
        ],
        env=env,
    )


def main() -> int:
    Path("dist").mkdir(exist_ok=True)
    build("main.py", "FingerprintLauncher.exe", [
          "--windows-console-mode=disable"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
