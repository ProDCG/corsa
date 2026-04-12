"""Nuitka build script for the Sled (rig agent) binary.

Produces a single standalone .exe that includes all dependencies.
Run on a Windows machine with Nuitka installed:
    python deploy/build_sled.py
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    ico = os.path.join("deploy", "ridge-link.ico")
    ico_flag = f"--windows-icon-from-ico={ico}" if os.path.exists(ico) else ""

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        f"--output-dir=build/sled",
        "--output-filename=CorsaConnect-Sled.exe",
        # Include the shared package
        "--include-package=shared",
        "--include-package=apps.sled",
        # Disable console window (runs as background service)
        "--windows-console-mode=disable",
        # Company metadata
        "--windows-product-name=CorsaConnect Sled",
        "--windows-company-name=Ridge Racing",
        "--windows-product-version=2.1.0",
        "--windows-file-description=CorsaConnect Rig Agent",
    ]

    if ico_flag:
        cmd.append(ico_flag)

    # Entry point
    cmd.append("apps/sled/main.py")

    print(f"Building Sled binary...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\n[OK] Sled binary built successfully!")
        print(f"   Output: build/sled/CorsaConnect-Sled.exe")
    else:
        print(f"\n[FAIL] Build failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
