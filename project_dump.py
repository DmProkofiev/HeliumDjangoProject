import os
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "project_dump.txt"

# включения
INCLUDE_EXT = {
    # backend
    ".py",
    # frontend
    ".js", ".jsx", ".mjs", ".ts", ".tsx",
    ".css", ".scss", ".sass",
    # разметка и данные
    ".html", ".htm", ".jinja", ".jinja2",
    ".json", ".yml", ".yaml", ".toml",
    ".cfg", ".ini", ".conf", ".txt", ".md",
    # прочее
    ".env.example", ".sql",
}
INCLUDE_NAMES = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "requirements.txt", "manage.py", "README.md", "README",
    "nginx.conf", "Procfile", "Makefile", ".env.example",
    "package.json", "package-lock.json",
}

# исключения
EXCLUDE_DIRS = {
    ".git", ".github", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "staticfiles", "media", "dist", "build",
    ".idea", ".vscode", "migrations",
}
EXCLUDE_FILES = {"db.sqlite3", "project_dump.txt", ".env", "project_tree.txt"}


def should_include(path: Path) -> bool:
    if path.name in EXCLUDE_FILES:
        return False
    if any(part in EXCLUDE_DIRS for part in path.relative_to(ROOT).parts):
        return False
    if path.name in INCLUDE_NAMES:
        return True
    return path.suffix.lower() in INCLUDE_EXT


def build_tree(root: Path) -> str:
    lines = [f"{root.name}/"]

    def walk(dir_path: Path, prefix: str = ""):
        try:
            entries = sorted(
                [e for e in dir_path.iterdir()
                 if e.name not in EXCLUDE_DIRS and e.name not in EXCLUDE_FILES],
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            last = i == len(entries) - 1
            connector = "└── " if last else "├── "
            lines.append(prefix + connector + entry.name + ("/" if entry.is_dir() else ""))
            if entry.is_dir():
                walk(entry, prefix + ("    " if last else "│   "))

    walk(root)
    return "\n".join(lines)


def main():
    parts = []
    parts.append("=" * 80)
    parts.append("PROJECT TREE")
    parts.append("=" * 80)
    parts.append(build_tree(ROOT))
    parts.append("")

    total = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if not should_include(fpath):
                continue
            rel = fpath.relative_to(ROOT)
            try:
                content = fpath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            parts.append(f"\n{'=' * 80}\n### FILE: {rel}\n{'=' * 80}\n")
            parts.append(content)
            parts.append("\n")
            total += 1

    OUT.write_text("".join(parts), encoding="utf-8")
    size_kb = OUT.stat().st_size // 1024
    print(f"Готово: {OUT} — {total} файлов, {size_kb} KB")

if __name__ == "__main__":
    main()