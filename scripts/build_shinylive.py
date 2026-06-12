from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_BUILD_DIR = ROOT / "_shinylive_app"
SITE_DIR = ROOT / "_site"
CACHE_DIR = ROOT / "shinylive-cache"

APP_FILES = (
    "app.py",
    "utils.py",
    "requirements.txt",
)

APP_DIRS = (
    "pages",
    "www",
)


def remove_inside_root(path: Path) -> None:
    resolved = path.resolve()
    root = ROOT.resolve()

    if root not in resolved.parents and resolved != root:
        raise RuntimeError(f"Refusing to remove path outside repository: {resolved}")

    if resolved.exists():
        shutil.rmtree(resolved)


def copy_app_files() -> None:
    remove_inside_root(APP_BUILD_DIR)
    APP_BUILD_DIR.mkdir()

    for filename in APP_FILES:
        shutil.copy2(ROOT / filename, APP_BUILD_DIR / filename)

    for dirname in APP_DIRS:
        shutil.copytree(
            ROOT / dirname,
            APP_BUILD_DIR / dirname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def export_site() -> None:
    remove_inside_root(SITE_DIR)
    CACHE_DIR.mkdir(exist_ok=True)

    from shinylive import _assets, _deps, _export
    from shinylive._version import SHINYLIVE_ASSETS_VERSION

    def cache_dir() -> str:
        return str(CACHE_DIR)

    def assets_dir(version: str = SHINYLIVE_ASSETS_VERSION) -> str:
        return str(CACHE_DIR / f"shinylive-{version}")

    _assets.shinylive_cache_dir = cache_dir
    _assets.shinylive_assets_dir = assets_dir
    _deps.shinylive_assets_dir = assets_dir
    _export.shinylive_assets_dir = assets_dir

    _export.export(APP_BUILD_DIR, SITE_DIR)
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    copy_app_files()
    export_site()


if __name__ == "__main__":
    main()
