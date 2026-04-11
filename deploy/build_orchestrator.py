"""Nuitka build script for the Orchestrator (admin) binary.

Produces a single standalone .exe that includes the FastAPI server
and the built React frontend (from frontend/dist).
Run on a Windows machine with Nuitka installed:
    python deploy/build_orchestrator.py
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(repo_root)

    # Build frontend first if dist doesn't exist
    frontend_dir = os.path.join("apps", "orchestrator", "frontend")
    dist_dir = os.path.join(frontend_dir, "dist")
    if not os.path.isdir(dist_dir):
        print("Building React frontend first...")
        npm = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm, "install"], cwd=frontend_dir, check=True)
        subprocess.run([npm, "run", "build"], cwd=frontend_dir, check=True)

    ico = os.path.join("deploy", "ridge-link.ico")
    ico_flag = f"--windows-icon-from-ico={ico}" if os.path.exists(ico) else ""

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        f"--output-dir=build/orchestrator",
        "--output-filename=CorsaConnect-Admin.exe",
        # Include packages
        "--include-package=shared",
        "--include-package=apps.orchestrator",
        # Bundle the built frontend
        f"--include-data-dir={dist_dir}=apps/orchestrator/frontend/dist",
        # Keep console visible (admin wants to see logs)
        "--windows-console-mode=force",
        # Company metadata
        "--windows-product-name=CorsaConnect Admin",
        "--windows-company-name=Ridge Racing",
        "--windows-product-version=2.1.0",
        "--windows-file-description=CorsaConnect Orchestrator",
    ]

    if ico_flag:
        cmd.append(ico_flag)

    # Entry point
    cmd.append("apps/orchestrator/main.py")

    print(f"Building Orchestrator binary...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\n✅ Orchestrator binary built successfully!")
        print(f"   Output: build/orchestrator/CorsaConnect-Admin.exe")
    else:
        print(f"\n❌ Build failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
