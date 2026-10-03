#!/usr/bin/env python3
"""Review a pull request's changed documents against their course rubrics.

For every ``docs/`` prefix in ``rubric-map.json`` that the pull request
touches, the whole document at ``head`` (every .tex/.md/.text file under the
prefix), the PR's diff for it, and the rubric text are sent to Gemini, which
returns a per-criterion assessment as JSON.  That is rendered with the
criteria losing marks first (reason and fix for each) and the rest folded
away, and the combined Markdown comment body is printed on stdout.  The first line is a hidden marker the workflow uses
to find and update its earlier comment instead of posting a new one on
every push.

The rubrics live in a private repo and are checked out separately; this
script only needs the directory they were checked out to.

Usage:  rubric_review.py --base <sha> --head <sha> --rubrics-dir <dir>
                         [--map .github/rubric-map.json] [--model <name>]
                         [--dry-run]

``GEMINI_API_KEY`` must be in the environment unless ``--dry-run`` is given,
which prints the prompts instead of calling the API.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

MARKER = "<!-- rubric-review -->"

# Newest stable Flash model on the free tier as of 2026-10. Override with
# --model (the workflow passes the GEMINI_MODEL repository variable when it
# is set); gemini-3.5-flash-lite has a much higher daily quota if this one's
# runs out.
DEFAULT_MODEL = "gemini-3.8-flash"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# The document source is what gets graded, so it is sent whole; the diff is
# there to tell the model what this PR actually changed. Both are capped so
# a big SRS doesn't blow past the request limit.
DOC_EXTENSIONS = (".tex", ".md", ".text")
MAX_DOC_CHARS = 250_000
MAX_DIFF_CHARS = 60_000

PROMPT = """\
You are a teaching assistant for a software engineering capstone course,
marking a team's document against the course rubric. Be direct and specific;
the team wants to know what would cost them marks, not encouragement.

The document is written in LaTeX. Judge the content, not the markup.

Assess every criterion in the rubric, in rubric order. For each one decide:

- "judged": you can assess it from the document. Give the level you would
  award (the rubric's own level name and points) and the top level's name
  and points for that criterion.
- "na": it cannot be judged from the document alone. This covers attendance
  at a presentation or demo, GitHub issues created for another team, code
  review interviews, and rows that belong to a different document when the
  rubric covers several (for example the Problem Statement rows when only
  the Development Plan is given). Do not score these as missing.

For a judged criterion that is below the top level, "why" must name the
concrete thing that is missing or wrong, pointing at the section or quoting
the document, and "fix" must say exactly what to add or change to reach the
top level. For a criterion already at the top level, "why" is one short
clause saying what earns it; "fix" is empty. Keep "why" under 30 words and
"fix" under 40 words. Never pad.

"pr_note" is one or two sentences: which criteria this PR's diff moved (if
any) and whether it introduced anything the rubric penalises.

=== RUBRIC ===
{rubric}

=== DOCUMENT (at the PR head) ===
{document}

=== DIFF (what this PR changed) ===
{diff}
"""

# Gemini is held to this shape so the comment can be rendered the same way
# every time, with the rows that lose marks pulled out in front.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["judged", "na"]},
                    "level": {"type": "string"},
                    "points": {"type": "number"},
                    "max_points": {"type": "number"},
                    "max_level": {"type": "string"},
                    "why": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["name", "status", "why"],
            },
        },
        "pr_note": {"type": "string"},
    },
    "required": ["criteria", "pr_note"],
}


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True,
                          text=True, errors="replace").stdout


def changed_files(base, head):
    # Three dots: only the PR's own changes, not what landed on base since.
    out = git("diff", "--name-only", "-M", f"{base}...{head}")
    return [line for line in out.splitlines() if line]


def document_text(head, prefix):
    """Concatenate every document source file under prefix at head."""
    paths = [p for p in git("ls-tree", "-r", "--name-only", head, "--", prefix)
             .splitlines() if p.endswith(DOC_EXTENSIONS)]
    chunks = []
    total = 0
    for path in sorted(paths):
        body = git("show", f"{head}:{path}")
        chunk = f"\n\n%%%% FILE: {path}\n{body}"
        if total + len(chunk) > MAX_DOC_CHARS:
            chunks.append(f"\n\n%%%% FILE: {path} (omitted: document too large)")
            continue
        chunks.append(chunk)
        total += len(chunk)
    return "".join(chunks).strip()


def diff_text(base, head, prefix):
    out = git("diff", "-M", f"{base}...{head}", "--", prefix)
    if len(out) > MAX_DIFF_CHARS:
        out = out[:MAX_DIFF_CHARS] + "\n... (diff truncated)"
    return out


def rubric_text(rubrics_dir, files):
    parts = []
    for name in files:
        path = os.path.join(rubrics_dir, name)
        with open(path, encoding="utf-8") as fh:
            parts.append(fh.read().strip())
    return "\n\n---\n\n".join(parts)


def call_gemini(model, api_key, prompt):
    """Return the model's JSON text. Retries the free tier's rate limiting."""
    url = API.format(model=model) + "?key=" + api_key
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }).encode()
    delay = 10
    for attempt in range(5):
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.load(resp)
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as err:
            # 429: free-tier quota (requests per minute); 503: overloaded.
            if err.code in (429, 503) and attempt < 4:
                print(f"gemini {err.code}, retrying in {delay}s",
                      file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            detail = err.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Gemini HTTP {err.code}: {detail}") from err
        except (KeyError, IndexError) as err:
            raise RuntimeError(f"Unexpected Gemini response: {data}") from err
    raise RuntimeError("Gemini: gave up after retries")


def render(review):
    """Turn the model's JSON into the comment body for one deliverable.

    Criteria that lose marks come first, each with the reason and the fix,
    since those are what the team acts on. Full-mark rows and rows that
    can't be judged from the document are folded away so they don't bury
    the rest.
    """
    short, full, na = [], [], []
    for c in review["criteria"]:
        if c.get("status") == "na":
            na.append(c)
        elif c.get("points") is not None and c.get("max_points") is not None \
                and c["points"] < c["max_points"]:
            short.append(c)
        else:
            full.append(c)

    def pts(c):
        level = c.get("level") or "?"
        if c.get("points") is None or c.get("max_points") is None:
            return level
        return f"{level} ({c['points']:g}/{c['max_points']:g})"

    out = [f"**{len(full)} ✅ full marks · {len(short)} ⚠️ losing marks · "
           f"{len(na)} ➖ not judged from the document**"]

    if short:
        out.append("### ⚠️ Losing marks")
        for c in sorted(short, key=lambda c: c["points"] - c["max_points"]):
            # Two or more levels down gets the louder icon.
            icon = "🔴" if c["max_points"] - c["points"] >= 2 else "⚠️"
            top = c.get("max_level") or "top level"
            out.append(f"**{icon} {c['name']}** — {pts(c)} → top is "
                       f"**{top}** ({c['max_points']:g})\n"
                       f"- **Why:** {c['why'].strip()}\n"
                       f"- **Fix:** {c.get('fix', '').strip() or 'n/a'}")
    else:
        out.append("### ✅ Nothing below the top level")

    if full:
        rows = "\n".join(f"- {c['name']} — {pts(c)}: {c['why'].strip()}"
                         for c in full)
        out.append(f"<details><summary>✅ Full marks ({len(full)})</summary>\n\n"
                   f"{rows}\n\n</details>")
    if na:
        rows = "\n".join(f"- {c['name']}: {c['why'].strip()}" for c in na)
        out.append(f"<details><summary>➖ Not judged from the document "
                   f"({len(na)})</summary>\n\n{rows}\n\n</details>")

    note = review.get("pr_note", "").strip()
    if note:
        out.append(f"**This PR:** {note}")
    return "\n\n".join(out)


def deliverables(mapping, files):
    """Yield (prefix, rubric files) for each mapped prefix the PR touched."""
    for prefix, rubrics in mapping.items():
        if prefix.startswith("_"):
            continue
        if any(f == prefix or f.startswith(prefix) for f in files):
            yield prefix, rubrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--rubrics-dir", required=True)
    ap.add_argument("--map", default=".github/rubric-map.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.map, encoding="utf-8") as fh:
        mapping = json.load(fh)

    hits = list(deliverables(mapping, changed_files(args.base, args.head)))
    if not hits:
        print(f"{MARKER}\nNo rubric-mapped documents changed in this pull request.")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(2)

    sections = [MARKER, "## Rubric review"]
    for prefix, rubrics in hits:
        prompt = PROMPT.format(
            rubric=rubric_text(args.rubrics_dir, rubrics),
            document=document_text(args.head, prefix),
            diff=diff_text(args.base, args.head, prefix),
        )
        title = f"## `{prefix}` — {', '.join(r[:-3] for r in rubrics)}"
        if args.dry_run:
            sections.append(f"{title}\n\n```\n{prompt}\n```")
            continue
        raw = ""
        try:
            raw = call_gemini(args.model, api_key, prompt)
            body = render(json.loads(raw))
        except RuntimeError as err:
            body = f"Review failed: {err}"
        except (ValueError, KeyError, TypeError) as err:
            # Schema-constrained output should always parse; if it doesn't,
            # show what came back rather than nothing.
            body = (f"Review came back in an unexpected shape ({err}):\n\n"
                    f"```\n{raw[:4000]}\n```")
        sections.append(f"{title}\n\n{body}")

    sections.append(f"<sub>Reviewed by `{args.model}` against the rubrics in "
                    "`capstoneCEGJM/rubrics`. Advisory only; a TA may read "
                    "it differently.</sub>")
    print("\n\n".join(sections))


if __name__ == "__main__":
    main()
