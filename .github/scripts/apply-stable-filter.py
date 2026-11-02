#!/usr/bin/env python3
from pathlib import Path
import re
import sys

TARGET = Path("sing-box.sh")

if not TARGET.exists():
    sys.exit("ERROR: sing-box.sh not found")

text = TARGET.read_text(encoding="utf-8")
original = text

# 当前上游通过 releases.atom 获取版本
atom_marker = "releases.atom"
api_marker = "api.github.com/repos/SagerNet/sing-box/releases"

# 排除预发布版本标签
stable_filter = (
    r"| grep -Ev '[-.](alpha|beta|rc|pre|dev|nightly)([.-]|$)' "
)

def patch_version_line(source, marker):
    lines = source.splitlines(keepends=True)
    matched = 0

    for i, line in enumerate(lines):
        if marker in line and "sort -Vr" in line:
            if "grep -Ev" not in line:
                lines[i] = line.replace(
                    "| sort -Vr",
                    stable_filter + "| sort -Vr",
                    1
                )
            matched += 1

    return "".join(lines), matched

text, atom_count = patch_version_line(text, atom_marker)
text, api_count = patch_version_line(text, api_marker)

# 网络获取失败时，使用稳定版兜底
text, fallback_count = re.subn(
    r"^DEFAULT_NEWEST_VERSION=.*$",
    "DEFAULT_NEWEST_VERSION='1.14.4'",
    text,
    count=1,
    flags=re.MULTILINE
)

if atom_count != 1:
    sys.exit(f"ERROR: expected 1 releases.atom version line, found {atom_count}")

if api_count != 1:
    sys.exit(f"ERROR: expected 1 GitHub API version line, found {api_count}")

if fallback_count != 1:
    sys.exit(f"ERROR: expected 1 DEFAULT_NEWEST_VERSION line, found {fallback_count}")

if text == original:
    print("Stable-only filter already applied.")
else:
    TARGET.write_text(text, encoding="utf-8")
    print("Stable-only filter applied.")
