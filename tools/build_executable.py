"""Recette de compilation Nuitka pour mini-metopes.

Produit un executable autonome (onefile) dans ``dist/`` a partir du point
d'entree ``src/mini_metopes/__main__.py``. Le repertoire ``dist/`` est ignore
par git : chaque poste doit regenerer son propre executable.

Usage :

    python -m pip install -e ".[build-exe]"
    python tools/build_executable.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Le paquet (et non __main__.py directement) : Nuitka doit voir le contexte
# de paquet pour resoudre les imports relatifs (`from .cli import main`).
ENTRY_POINT = REPO_ROOT / "src" / "mini_metopes"
RESOURCES_DIR = REPO_ROOT / "src" / "mini_metopes" / "resources"
DIST_DIR = REPO_ROOT / "dist"


def build() -> int:
    output_filename = "mini-metopes.exe" if sys.platform == "win32" else "mini-metopes"
    command = [
        sys.executable,
        "-m", "nuitka",
        "--onefile",
        "--assume-yes-for-downloads",
        "--python-flag=-m",
        "--enable-plugin=tk-inter",
        f"--include-data-dir={RESOURCES_DIR}=mini_metopes/resources",
        f"--output-dir={DIST_DIR}",
        f"--output-filename={output_filename}",
        str(ENTRY_POINT),
    ]
    if sys.platform == "win32":
        # Pas de company-name/product-name/file-version/product-version : ces
        # options declenchent l'embarquement de ressources VERSIONINFO dans
        # l'executable, une etape que les antivirus (ex. Windows Defender)
        # font souvent echouer en verrouillant le fichier en cours d'ecriture.
        command[3:3] = ["--windows-console-mode=force"]
    print("+ " + " ".join(command))
    result = subprocess.run(command, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(build())
