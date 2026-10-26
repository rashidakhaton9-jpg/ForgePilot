#!/usr/bin/env python3
"""ForgePilot: read-only repository reconnaissance helpers; Python standard library only."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules",
    "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build",
    "target", ".next", ".nuxt", "vendor"
}
MARKERS = [
    "README.md", "README", "AGENTS.md", "CONTRIBUTING.md",
    "pyproject.toml", "requirements.txt", "package.json", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle", "Makefile", " justfile",
    "pytest.ini", "tox.ini", ".github/workflows"
]
MAX_FILES = 10000
MAX_DEPTH = 12


def walk_files(root: Path):
    root = root.resolve()
    count = 0
    for current, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        cur = Path(current)
        try:
            depth = len(cur.relative_to(root).parts)
        except ValueError:
            dirs[:] = []
            continue
        dirs[:] = sorted(
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
            and not (cur / d).is_symlink()
        )
        if depth >= MAX_DEPTH:
            dirs[:] = []
        for filename in sorted(filenames):
            path = cur / filename
            if path.is_symlink():
                continue
            yield path
            count += 1
            if count >= MAX_FILES:
                return


def inventory(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    files = list(walk_files(root))
    extensions = Counter((p.suffix.lower() or "[no extension]") for p in files)
    markers = []
    for marker in MARKERS:
        candidate = root / marker.strip()
        if candidate.exists():
            markers.append(marker.strip())
    return {
        "root": str(root),
        "files_scanned": len(files),
        "truncated": len(files) >= MAX_FILES,
        "extensions": dict(extensions.most_common()),
        "markers_found": markers,
        "sample_files": [
            str(p.relative_to(root)) for p in files[:80]
        ],
    }


def checks(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    results = []
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    readmes = [root / "README.md", root / "README", root / "README.rst"]
    results.append({
        "status": "PASS" if any(p.is_file() for p in readmes) else "WARN",
        "check": "README exists",
        "detail": "Found a README." if any(p.is_file() for p in readmes)
                  else "No common README filename found."
    })

    git_dir = root / ".git"
    results.append({
        "status": "INFO" if git_dir.exists() else "WARN",
        "check": "Git metadata",
        "detail": "Found .git metadata." if git_dir.exists()
                  else "No .git directory found; this may be a downloaded archive."
    })

    test_markers = [
        root / "tests", root / "test", root / "pytest.ini",
        root / "tox.ini", root / "package.json"
    ]
    has_tests = any(p.exists() for p in test_markers)
    results.append({
        "status": "INFO" if has_tests else "WARN",
        "check": "Test marker",
        "detail": "Found a likely test/config marker; inspect it to confirm."
                  if has_tests else "No common test marker found."
    })

    ignore = root / ".gitignore"
    results.append({
        "status": "PASS" if ignore.is_file() else "WARN",
        "check": ".gitignore exists",
        "detail": "Found .gitignore." if ignore.is_file()
                  else "No .gitignore found; consider excluding caches, secrets, and generated files."
    })

    return results


def emit(data: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if isinstance(data, dict) and "extensions" in data:
        print(f"ForgePilot repository inspection: {data['root']}")
        print(f"Files scanned: {data['files_scanned']}" +
              (" (scan limit reached)" if data["truncated"] else ""))
        print("\nProject markers:")
        print("  " + (", ".join(data["markers_found"]) or "None of the common markers found"))
        print("\nFile extensions:")
        for ext, count in data["extensions"].items():
            print(f"  {ext}: {count}")
        print("\nSample files:")
        for name in data["sample_files"]:
            print(f"  {name}")
    elif isinstance(data, list):
        for item in data:
            print(f"[{item['status']}] {item['check']}: {item['detail']}")
    elif isinstance(data, dict) and "inspection" in data and "checks" in data:
        emit(data["inspection"], False)
        print("\nStructural checks:")
        emit(data["checks"], False)
    else:
        print(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="forgepilot",
        description="Read-only repository inspection helpers. Does not execute project code."
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("inspect", "Summarize files and project markers"),
        ("check", "Run basic structural checks"),
        ("report", "Print a combined inspection and check report"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")

    args = parser.parse_args(argv)
    root = Path(args.path)

    try:
        if args.command == "inspect":
            emit(inventory(root), args.json)
        elif args.command == "check":
            emit(checks(root), args.json)
        elif args.command == "report":
            report = {"inspection": inventory(root), "checks": checks(root)}
            emit(report, args.json)
        return 0
    except (OSError, ValueError) as exc:
        print(f"forgepilot: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
