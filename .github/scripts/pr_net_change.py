#!/usr/bin/env python3
"""Summarise a pull request's net line change, leaving out tests.

Compares ``head`` against its merge base with ``base`` (the same three-dot
diff GitHub shows on the "Files changed" tab) and prints a Markdown comment
body on stdout.  The first line is a hidden marker the workflow uses to find
and update its earlier comment instead of posting a new one on every push.

Tests are recognised by path only.  A Rust ``#[cfg(test)] mod tests`` block
inside an ordinary source file therefore still counts as source.

Usage:  pr_net_change.py --base <sha> --head <sha>
"""

import argparse
import fnmatch
import subprocess
import sys

MARKER = "<!-- pr-net-change -->"

# Any path component with one of these names puts the file under test.
TEST_DIRS = {"test", "tests", "__tests__", "testdata", "benches"}

# Filenames that are tests wherever they live.
TEST_FILE_PATTERNS = ("*_test.*", "*_tests.*", "test_*.py", "*.test.*",
                      "*.spec.*", "tests.rs")

# Written by CI, not by the author of the pull request.
GENERATED_PREFIXES = ("pdfs/",)
GENERATED_PATHS = {".pdf-deps.json"}


def classify(path):
    """Return "test", "generated" or "source" for a repository path."""
    if path in GENERATED_PATHS or path.startswith(GENERATED_PREFIXES):
        return "generated"
    parts = path.split("/")
    if any(part in TEST_DIRS for part in parts[:-1]):
        return "test"
    if any(fnmatch.fnmatch(parts[-1], pat) for pat in TEST_FILE_PATTERNS):
        return "test"
    return "source"


def numstat(base, head):
    """Yield (added, deleted, path) for each file, None counts for binaries."""
    # git diff --numstat -z -M base...head:
    #   --numstat  one line per changed file: lines added, lines deleted and
    #              the path, separated by tabs. Binary files have no line
    #              counts, so both show "-".
    #   -M         detects renames, so a moved file is counted by what
    #              changed in it rather than as a whole delete plus add.
    #   base...head
    #              three dots diff head against its merge base with base,
    #              so only the pull request's own changes are counted, not
    #              whatever landed on base since the branch was made.
    #   -z         ends each record with a NUL instead of a newline and
    #              leaves paths unquoted, so any filename parses safely.
    #
    # Without -z, a changed file, a binary file and a rename look like:
    #
    #   2       0       README.md
    #   -       -       logo.png
    #   1       0       old.py => new.py
    #
    # With -z (each record on its own line here for readability), the
    # rename's two paths get their own NUL-ended fields:
    #
    #   2\t0\tREADME.md\0
    #   -\t-\tlogo.png\0
    #   1\t0\t\0old.py\0new.py\0
    out = subprocess.run(
        ["git", "diff", "--numstat", "-z", "-M", f"{base}...{head}"],
        check=True, capture_output=True, text=True).stdout
    # fields is that output split on NUL, so for the example above:
    #
    #   ["2\t0\tREADME.md", "-\t-\tlogo.png", "1\t0\t", "old.py", "new.py", ""]
    #
    # i is the index of the next record's counts. A normal file uses one
    # field, and a rename uses three (counts with an empty path, old path,
    # new path). The trailing NUL leaves an empty last field, which ends the
    # loop.
    fields = out.split("\0")
    i = 0
    while i < len(fields) and fields[i]:
        added, deleted, path = fields[i].split("\t", 2)
        i += 1
        if not path:
            # A rename: -z puts the old and new paths in the next two fields.
            path = fields[i + 1]
            i += 2
        if added == "-":
            yield None, None, path
        else:
            yield int(added), int(deleted), path


def signed(n):
    return f"+{n}" if n > 0 else f"−{-n}" if n < 0 else "0"


# GitHub Markdown has no text colour, but its math rendering does. The
# $`...`$ form keeps the table's Markdown from touching the TeX inside.
GREEN_PLUS = r"$`\color{green}+`$"
RED_MINUS = r"$`\color{red}-`$"


def colored(n):
    """A net line count with its sign drawn green or red."""
    if n > 0:
        return f"{GREEN_PLUS} {n}"
    if n < 0:
        return f"{RED_MINUS} {-n}"
    return "0"


def render(rows):
    totals = {kind: [0, 0, 0] for kind in ("source", "test", "generated")}
    source_rows = []
    for added, deleted, path in rows:
        kind = classify(path)
        totals[kind][2] += 1
        if added is None:
            if kind == "source":
                source_rows.append((path, "binary", "", ""))
            continue
        totals[kind][0] += added
        totals[kind][1] += deleted
        if kind == "source":
            source_rows.append((path, f"+{added}", f"−{deleted}",
                                signed(added - deleted)))

    lines = [MARKER, "",
             "| | Files | Added | Deleted | Net |", "|---|--:|--:|--:|--:|"]
    for label, kind in (("Test", "test"), ("Prod", "source")):
        added, deleted, files = totals[kind]
        lines.append(f"| {label} | {files} | {GREEN_PLUS} {added} "
                     f"| {RED_MINUS} {deleted} | {colored(added - deleted)} |")
    lines.append("")
    if totals["generated"][2]:
        lines.append(f"CI-generated files, not counted: "
                     f"{totals['generated'][2]}.")
    if source_rows:
        source_rows.sort(key=lambda r: r[0])
        lines += ["", "<details><summary>Files counted</summary>", "",
                  "| File | Added | Deleted | Net |", "|---|--:|--:|--:|"]
        # An unescaped | in a filename would end the table cell early
        lines += [f"| `{p.replace('|', chr(92) + '|')}` | {a} | {d} | {n} |"
                  for p, a, d, n in source_rows]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    sys.stdout.write(render(numstat(args.base, args.head)))


if __name__ == "__main__":
    main()
