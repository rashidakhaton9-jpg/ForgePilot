#!/usr/bin/env python3
"""Validate ForgePilot's Agent Skill metadata and local references (stdlib only)."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["SKILL.md is missing"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ["SKILL.md must start with YAML frontmatter delimited by ---"]
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ["SKILL.md frontmatter closing delimiter is missing"]
    frontmatter = parts[1]
    name = re.search(r"(?m)^name:\s*([a-z0-9-]+)\s*$", frontmatter)
    description = re.search(r"(?m)^description:\s*(.+?)\s*$", frontmatter)
    if not name:
        errors.append("Frontmatter must contain a lowercase hyphenated name")
    elif len(name.group(1)) > 64:
        errors.append("Skill name must be 64 characters or fewer")
    if not description:
        errors.append("Frontmatter must contain a description")
    elif len(description.group(1)) > 1024:
        errors.append("Description must be 1024 characters or fewer")

    for ref in re.findall(r"`((?:scripts|references)/[^`]+)`", text):
        target = root / ref
        if not target.exists():
            errors.append(f"Referenced path does not exist: {ref}")
    for required in ("README.md", ".gitignore", "LICENSE"):
        if not (root / required).is_file():
            errors.append(f"Required project file is missing: {required}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("ForgePilot skill validation FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ForgePilot skill validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
