from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "desktop" / "resources" / "prebuilt"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build" / "pyinstaller"
    dist = ROOT / "build" / "backend-dist"
    for path in (work, dist):
        if path.exists():
            shutil.rmtree(path)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--name", "crossborder-backend", "--paths", str(ROOT / "src"),
        "--collect-all", "uvicorn", "--collect-all", "pydantic", "--collect-all", "openpyxl",
        "--distpath", str(dist), "--workpath", str(work),
        "--specpath", str(work), str(ROOT / "scripts" / "backend_entry.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    binary = dist / ("crossborder-backend.exe" if sys.platform == "win32" else "crossborder-backend")
    if not binary.is_file():
        raise SystemExit(f"Backend binary was not created: {binary}")
    target = OUTPUT / binary.name
    shutil.copy2(binary, target)
    print(target)


if __name__ == "__main__":
    main()
