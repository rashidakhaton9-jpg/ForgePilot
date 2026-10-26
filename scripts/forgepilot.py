#!/usr/bin/env python3
"""ForgePilot — bounded, read-only repository intelligence CLI (Python stdlib only).

This tool inventories and structurally analyzes a repository. It does not execute
project code, install dependencies, change files, or make network requests.
Findings are heuristics, not proof of correctness or security.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.2.0"
DEFAULT_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", "target", ".next", ".nuxt", ".turbo", "vendor",
    "coverage", "htmlcov", "site-packages",
}
MARKERS = [
    "README.md", "README", "README.rst", "AGENTS.md", "CONTRIBUTING.md",
    "pyproject.toml", "requirements.txt", "Pipfile", "package.json",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Makefile",
    "justfile", "pytest.ini", "tox.ini", ".github/workflows",
    "Dockerfile", "compose.yaml", "docker-compose.yml", "tsconfig.json",
]
LANGUAGE_BY_EXT = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript", ".jsx": "JavaScript/JSX", ".ts": "TypeScript",
    ".tsx": "TypeScript/JSX", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C/C++ header", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".php": "PHP", ".rb": "Ruby", ".swift": "Swift",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".bat": "Batch",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".json": "JSON",
    ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".xml": "XML",
    ".md": "Markdown", ".rst": "reStructuredText", ".sql": "SQL",
    ".ipynb": "Jupyter Notebook", ".vue": "Vue", ".svelte": "Svelte",
}
CONFIG_NAMES = {
    ".editorconfig", ".gitignore", ".gitattributes", ".prettierrc", ".prettierrc.json",
    ".eslintrc", ".eslintrc.json", "ruff.toml", ".ruff.toml", "mypy.ini",
    "pyrightconfig.json", "tsconfig.json", "biome.json", "biome.jsonc",
}
TEST_NAME_RE = re.compile(r"(^|[/_.-])(test|tests|spec|specs)([/_.-]|$)", re.I)
SECRET_NAME_RE = re.compile(r"(^|[._-])(\.env|secrets?|credentials?|private[_-]?key|id_rsa|token)([._-]|$)", re.I)
TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".java", ".kt",
    ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".rb", ".swift",
    ".sh", ".bash", ".ps1", ".bat", ".html", ".css", ".scss", ".json", ".yaml",
    ".yml", ".toml", ".xml", ".md", ".rst", ".sql", ".vue", ".svelte", ".txt",
    ".ini", ".cfg", ".conf", ".properties", ".gradle", ".dockerfile",
}


def _validate_root(root: Path) -> Path:
    try:
        resolved = root.expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve path {root}: {exc}") from exc
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Not a directory: {resolved}")
    return resolved


def walk_files(root: Path, *, max_files: int = 10000, max_depth: int = 12,
               include_hidden: bool = False, excludes: Iterable[str] = ()):
    """Yield regular files without following symlinks; bounds protect huge trees."""
    root = _validate_root(root)
    if max_files < 1 or max_depth < 0:
        raise ValueError("max_files must be >= 1 and max_depth must be >= 0")
    excludes = tuple(excludes)
    yielded = 0
    for current, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        cur = Path(current)
        try:
            depth = len(cur.relative_to(root).parts)
        except ValueError:
            dirs[:] = []
            continue
        kept = []
        for dirname in sorted(dirs):
            candidate = cur / dirname
            rel = candidate.relative_to(root).as_posix()
            if dirname in DEFAULT_SKIP_DIRS or candidate.is_symlink():
                continue
            if not include_hidden and dirname.startswith("."):
                continue
            if any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(dirname, pattern) for pattern in excludes):
                continue
            if depth < max_depth:
                kept.append(dirname)
        dirs[:] = kept
        for filename in sorted(filenames):
            path = cur / filename
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if not include_hidden and any(part.startswith(".") for part in Path(rel).parts):
                continue
            if any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(filename, pattern) for pattern in excludes):
                continue
            yield path
            yielded += 1
            if yielded >= max_files:
                return


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def inventory(root: Path, *, max_files: int = 10000, max_depth: int = 12,
              include_hidden: bool = False, excludes: Iterable[str] = ()) -> dict[str, Any]:
    root = _validate_root(root)
    files = list(walk_files(root, max_files=max_files, max_depth=max_depth,
                            include_hidden=include_hidden, excludes=excludes))
    ext_counts = Counter((p.suffix.lower() or "[no extension]") for p in files)
    lang_counts = Counter(LANGUAGE_BY_EXT.get(p.suffix.lower(), "Other") for p in files)
    markers = [m for m in MARKERS if (root / m).exists()]
    sizes = []
    total_bytes = 0
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        sizes.append({"path": _relative(path, root), "bytes": size})
    sizes.sort(key=lambda x: (-x["bytes"], x["path"]))
    count_limit_reached = len(files) >= max_files
    return {
        "tool": "ForgePilot", "version": VERSION, "root": str(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files_scanned": len(files), "truncated": count_limit_reached,
        "limits": {"max_files": max_files, "max_depth": max_depth,
                   "include_hidden": include_hidden, "exclude_patterns": list(excludes)},
        "total_bytes_scanned": total_bytes,
        "extensions": dict(ext_counts.most_common()),
        "languages": dict(lang_counts.most_common()),
        "markers_found": markers,
        "largest_files": sizes[:15],
        "sample_files": [_relative(p, root) for p in files[:100]],
    }


def _check(status: str, name: str, detail: str, *, evidence: str | None = None) -> dict[str, str]:
    item = {"status": status, "check": name, "detail": detail}
    if evidence:
        item["evidence"] = evidence
    return item


def checks(root: Path, *, max_files: int = 10000, max_depth: int = 12,
           include_hidden: bool = False, excludes: Iterable[str] = ()) -> list[dict[str, str]]:
    root = _validate_root(root)
    results: list[dict[str, str]] = []
    readmes = [root / "README.md", root / "README", root / "README.rst"]
    found_readme = next((p for p in readmes if p.is_file()), None)
    results.append(_check("PASS" if found_readme else "WARN", "README exists",
                          "Found a README." if found_readme else "No common README filename found.",
                          evidence=_relative(found_readme, root) if found_readme else None))
    git_dir = root / ".git"
    results.append(_check("INFO" if git_dir.exists() else "WARN", "Git metadata",
                          "Found .git metadata." if git_dir.exists() else
                          "No .git directory found; this may be a downloaded archive."))
    files = list(walk_files(root, max_files=max_files, max_depth=max_depth,
                            include_hidden=include_hidden, excludes=excludes))
    rels = [_relative(p, root) for p in files]
    test_files = [name for name in rels if TEST_NAME_RE.search(name)]
    has_test_config = any((root / name).exists() for name in ("pytest.ini", "tox.ini", "vitest.config.ts", "jest.config.js"))
    results.append(_check("INFO" if (test_files or has_test_config) else "WARN", "Test evidence",
                          f"Found {len(test_files)} likely test/spec path(s)" + (" and/or test config." if has_test_config else ".")
                          if (test_files or has_test_config) else "No obvious test/spec paths or common test config found.",
                          evidence=", ".join(test_files[:5]) if test_files else None))
    ignore = root / ".gitignore"
    results.append(_check("PASS" if ignore.is_file() else "WARN", ".gitignore exists",
                          "Found .gitignore." if ignore.is_file() else
                          "No .gitignore found; consider excluding caches, secrets, and generated files."))
    configs = [name for name in rels if Path(name).name in CONFIG_NAMES]
    results.append(_check("INFO" if configs else "WARN", "Tooling configuration",
                          f"Found {len(configs)} likely formatter/linter/type-checker config file(s)." if configs
                          else "No common editor/linter/formatter configuration found.",
                          evidence=", ".join(configs[:8]) if configs else None))
    secret_names = [name for name in rels if SECRET_NAME_RE.search(Path(name).name)]
    results.append(_check("WARN" if secret_names else "PASS", "Sensitive-looking filenames",
                          f"Review {len(secret_names)} sensitive-looking filename(s); names alone do not prove secrets are exposed."
                          if secret_names else "No obvious sensitive-looking filenames found in scanned paths.",
                          evidence=", ".join(secret_names[:10]) if secret_names else None))
    oversized = []
    for path in files:
        try:
            if path.stat().st_size > 2_000_000:
                oversized.append(f"{_relative(path, root)} ({path.stat().st_size} bytes)")
        except OSError:
            pass
    results.append(_check("WARN" if oversized else "INFO", "Large files",
                          f"Found {len(oversized)} file(s) larger than 2 MB; inspect whether generated/binary files belong in source control."
                          if oversized else "No scanned files exceed 2 MB." ,
                          evidence=", ".join(oversized[:8]) if oversized else None))
    return results


def search_text(root: Path, query: str, *, regex: bool = False, ignore_case: bool = False,
                max_files: int = 10000, max_depth: int = 12, include_hidden: bool = False,
                excludes: Iterable[str] = (), max_matches: int = 200,
                max_file_bytes: int = 1_000_000) -> dict[str, Any]:
    root = _validate_root(root)
    if not query:
        raise ValueError("Search query cannot be empty")
    if max_matches < 1:
        raise ValueError("max_matches must be >= 1")
    try:
        pattern = re.compile(query, re.I if ignore_case else 0) if regex else None
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc
    matches = []
    skipped_binary_or_large = 0
    files_scanned = 0
    for path in walk_files(root, max_files=max_files, max_depth=max_depth,
                            include_hidden=include_hidden, excludes=excludes):
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile", "Justfile"}:
            continue
        files_scanned += 1
        try:
            if path.stat().st_size > max_file_bytes:
                skipped_binary_or_large += 1
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            found = bool(pattern.search(line)) if regex else (query.casefold() in line.casefold() if ignore_case else query in line)
            if found:
                matches.append({"path": _relative(path, root), "line": line_no, "text": line[:500]})
                if len(matches) >= max_matches:
                    return {"query": query, "regex": regex, "files_scanned": files_scanned,
                            "matches": matches, "truncated": True,
                            "skipped_large_or_unreadable_candidates": skipped_binary_or_large}
    return {"query": query, "regex": regex, "files_scanned": files_scanned,
            "matches": matches, "truncated": False,
            "skipped_large_or_unreadable_candidates": skipped_binary_or_large}


def build_report(root: Path, **options: Any) -> dict[str, Any]:
    inv = inventory(root, **options)
    chks = checks(root, **options)
    counts = Counter(item["status"] for item in chks)
    return {
        "tool": "ForgePilot", "version": VERSION, "report_type": "read-only repository reconnaissance",
        "inspection": inv, "checks": chks,
        "summary": {"checks_total": len(chks), "pass": counts["PASS"], "info": counts["INFO"],
                    "warn": counts["WARN"], "critical_claims": "none; findings are heuristic"},
        "recommended_next_steps": _next_steps(inv, chks),
        "limitations": [
            "Does not execute project code or tests.",
            "Does not install dependencies or access the network.",
            "Filename and structure checks are heuristics, not a security audit.",
            "A successful report does not prove the project builds or behaves correctly.",
        ],
    }


def _next_steps(inv: dict[str, Any], chks: list[dict[str, str]]) -> list[str]:
    steps = []
    if "README.md" not in inv["markers_found"] and "README" not in inv["markers_found"]:
        steps.append("Add or locate a README that explains setup, usage, and supported environments.")
    if any(c["check"] == "Test evidence" and c["status"] == "WARN" for c in chks):
        steps.append("Identify the project test command and add focused regression tests for important behavior.")
    if any(c["check"] == "Sensitive-looking filenames" and c["status"] == "WARN" for c in chks):
        steps.append("Manually inspect sensitive-looking paths; never print or upload secret contents to diagnose them.")
    if inv.get("truncated"):
        steps.append("Repeat the scan with a higher --max-files value if the omitted tail matters.")
    steps.append("Read project-specific instructions before editing, then run the repository's documented checks separately.")
    return steps


def emit(data: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if isinstance(data, dict) and "extensions" in data and "sample_files" in data:
        print(f"ForgePilot v{data.get('version', VERSION)} — repository inspection")
        print(f"Root: {data['root']}\nFiles scanned: {data['files_scanned']}" + (" (limit reached)" if data["truncated"] else ""))
        print(f"Approximate file bytes: {data.get('total_bytes_scanned', 0):,}")
        print("\nProject markers: " + (", ".join(data["markers_found"]) or "none detected"))
        print("\nLanguages:")
        for name, count in data.get("languages", {}).items(): print(f"  {name}: {count}")
        print("\nLargest files:")
        for item in data.get("largest_files", [])[:10]: print(f"  {item['bytes']:>10,} B  {item['path']}")
        print("\nSample paths:")
        for name in data["sample_files"][:40]: print(f"  {name}")
    elif isinstance(data, list) and all(isinstance(x, dict) and "check" in x for x in data):
        for item in data:
            evidence = f" | evidence: {item['evidence']}" if item.get("evidence") else ""
            print(f"[{item['status']}] {item['check']}: {item['detail']}{evidence}")
    elif isinstance(data, dict) and "inspection" in data and "checks" in data:
        emit(data["inspection"])
        print("\nStructural checks:")
        emit(data["checks"])
        if data.get("summary"):
            s = data["summary"]
            print(f"\nSummary: {s['checks_total']} checks — {s['pass']} PASS, {s['info']} INFO, {s['warn']} WARN")
        if data.get("recommended_next_steps"):
            print("\nRecommended next steps:")
            for i, step in enumerate(data["recommended_next_steps"], 1): print(f"  {i}. {step}")
        if data.get("limitations"):
            print("\nLimitations:")
            for item in data["limitations"]: print(f"  - {item}")
    elif isinstance(data, dict) and "matches" in data:
        print(f"Search: {data['query']!r} — {len(data['matches'])} match(es) in {data['files_scanned']} file(s)")
        for item in data["matches"]:
            print(f"{item['path']}:{item['line']}: {item['text']}")
        if data["truncated"]: print("Match output limit reached; narrow the query or increase --max-matches.")
        if data["skipped_large_or_unreadable_candidates"]: print(f"Skipped large/unreadable candidates: {data['skipped_large_or_unreadable_candidates']}")
    else:
        print(data)


def add_scan_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    parser.add_argument("--max-files", type=int, default=10000, help="Maximum files to scan (default: 10000)")
    parser.add_argument("--max-depth", type=int, default=12, help="Maximum directory depth (default: 12)")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden paths (except symlinks and skipped dependency/build dirs)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="Exclude matching path/name; repeatable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="forgepilot",
        description="ForgePilot: bounded, read-only repository reconnaissance. No project execution, installs, writes, or network access.",
        epilog="Examples: forgepilot report . --json | forgepilot search 'TODO' . --ignore-case | forgepilot check . --max-files 20000",
    )
    parser.add_argument("--version", action="version", version=f"ForgePilot {VERSION}")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON (place before subcommand)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("inspect", "Inventory files, languages, markers, and largest files"),
        ("check", "Run structural and lightweight hygiene checks"),
        ("report", "Produce a combined report with evidence, limits, and next steps"),
    ]:
        p = sub.add_parser(name, help=help_text)
        add_scan_options(p)
        p.add_argument("--json", action="store_true", dest="json_sub", help=argparse.SUPPRESS)
    s = sub.add_parser("search", help="Search source-like text files without executing them")
    s.add_argument("query", help="Literal text or regular expression")
    add_scan_options(s)
    s.add_argument("--regex", action="store_true", help="Interpret query as a regular expression")
    s.add_argument("--ignore-case", action="store_true", help="Search case-insensitively")
    s.add_argument("--max-matches", type=int, default=200, help="Maximum matches to return (default: 200)")
    s.add_argument("--max-file-bytes", type=int, default=1_000_000, help="Skip files larger than this size (default: 1000000)")
    s.add_argument("--json", action="store_true", dest="json_sub", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(getattr(args, "path", "."))
    options = {"max_files": getattr(args, "max_files", 10000),
               "max_depth": getattr(args, "max_depth", 12),
               "include_hidden": getattr(args, "include_hidden", False),
               "excludes": getattr(args, "exclude", [])}
    try:
        if args.command == "inspect": data = inventory(root, **options)
        elif args.command == "check": data = checks(root, **options)
        elif args.command == "report": data = build_report(root, **options)
        elif args.command == "search":
            data = search_text(root, args.query, regex=args.regex, ignore_case=args.ignore_case,
                               max_matches=args.max_matches, max_file_bytes=args.max_file_bytes, **options)
        else:
            parser.error("Unknown command")
            return 2
        emit(data, args.json or getattr(args, "json_sub", False))
        if args.command == "check" and any(x["status"] == "WARN" for x in data):
            return 1
        return 0
    except (OSError, ValueError) as exc:
        print(f"forgepilot: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
