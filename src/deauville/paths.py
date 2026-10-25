"""Locate the project folder (data/ and web/), even if the command is run elsewhere."""

from pathlib import Path


def project_root() -> Path:
    here = Path(__file__).resolve()
    for folder in here.parents:
        if (folder / "web" / "public").is_dir() and (
            folder / "data" / "festival.json"
        ).is_file():
            return folder
    return Path.cwd()
