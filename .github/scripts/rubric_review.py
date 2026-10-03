#!/usr/bin/env python3
"""Review a pull request's changed documents against their course rubrics.

For every ``docs/`` prefix in ``rubric-map.json`` the PR touches, the whole
document at ``head``, the PR's diff for it and the rubric text go to Gemini,
which returns a per-criterion assessment as JSON.  It is rendered with the
criteria losing marks first (reason and fix for each), the rest folded away,
and printed on stdout as a Markdown comment.  The first line is a marker the
workflow uses to update its earlier comment instead of posting a new one.

Usage:  rubric_review.py --base <sha> --head <sha> --rubrics-dir <dir>
                         [--map <json>] [--model <name>] [--dry-run]
``GEMINI_API_KEY`` must be set unless ``--dry-run`` (prints the prompts).
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
# Newest stable Flash on the free tier as of 2026-10; the fallback has a much
# higher daily quota and is used when the first is still rate limited after
# the retries.
DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

# The document is graded whole; the diff only says what this PR changed.
# Both are capped so a big SRS doesn't blow past the request limit.
DOC_EXTENSIONS = (".tex", ".md", ".text")
MAX_DOC_CHARS = 250_000
MAX_DIFF_CHARS = 60_000

PROMPT = """\
You are a teaching assistant for a software engineering capstone course,
marking a team's document against the course rubric. Be direct and specific;
the team wants to know what would cost them marks, not encouragement. The
document is LaTeX: judge the content, not the markup.

Assess every rubric criterion, in rubric order. Each is either
- "judged": assessable from the document. Give the level you would award
  (the rubric's own level name and points) and the top level's name and
  points for that criterion; or
- "na": not assessable from the document alone: attendance at a presentation
  or demo, GitHub issues created for another team, code review interviews,
  and rows belonging to a different document when the rubric covers several
  (e.g. Problem Statement rows when only the Development Plan is given).
  Never score these as missing.

Below the top level, "why" names the concrete thing missing or wrong,
pointing at the section or quoting the document, and "fix" says exactly what
to add or change to reach the top level. At the top level, "why" is one
short clause on what earns it and "fix" is empty. "why" under 30 words,
"fix" under 40. "pr_note" is one or two sentences: which criteria this PR's
diff moved, if any, and whether it introduced anything the rubric penalises.

=== RUBRIC ===
{rubric}

=== DOCUMENT (at the PR head) ===
{document}

=== DIFF (what this PR changed) ===
{diff}
"""

# Gemini is held to this shape so the comment renders the same way every time.
_FIELDS = {"name": "string", "status": "string", "level": "string",
           "points": "number", "max_points": "number", "max_level": "string",
           "why": "string", "fix": "string"}
RESPONSE_SCHEMA = {
    "type": "object", "required": ["criteria", "pr_note"],
    "properties": {
        "pr_note": {"type": "string"},
        "criteria": {"type": "array", "items": {
            "type": "object", "required": ["name", "status", "why"],
            "properties": {k: {"type": t} for k, t in _FIELDS.items()}}}}}
RESPONSE_SCHEMA["properties"]["criteria"]["items"]["properties"]["status"][
    "enum"] = ["judged", "na"]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True,
                          text=True, errors="replace").stdout


def document_text(head, prefix):
    """Concatenate every document source file under prefix at head."""
    chunks, total = [], 0
    for path in sorted(git("ls-tree", "-r", "--name-only", head, "--", prefix)
                       .splitlines()):
        if not path.endswith(DOC_EXTENSIONS):
            continue
        chunk = f"\n\n%%%% FILE: {path}\n{git('show', f'{head}:{path}')}"
        if total + len(chunk) > MAX_DOC_CHARS:
            chunk = f"\n\n%%%% FILE: {path} (omitted: document too large)"
        chunks.append(chunk)
        total += len(chunk)
    return "".join(chunks).strip()


def call_gemini(model, api_key, prompt):
    """Return the model's JSON text. Retries the free tier's rate limiting."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2,
                             "responseMimeType": "application/json",
                             "responseSchema": RESPONSE_SCHEMA}}).encode()
    req = urllib.request.Request(API.format(model) + "?key=" + api_key,
                                 data=body,
                                 headers={"Content-Type": "application/json"})
    delay = 10
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.load(resp)
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as err:
            # 429: free-tier requests per minute; 503: overloaded.
            if err.code in (429, 503) and attempt < 4:
                print(f"gemini {err.code}, retrying in {delay}s", file=sys.stderr)
                time.sleep(delay)
                delay *= 2
                continue
            detail = err.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Gemini HTTP {err.code}: {detail}") from err
        except (KeyError, IndexError) as err:
            raise RuntimeError(f"Unexpected Gemini response: {data}") from err
    raise QuotaExhausted(model)


class QuotaExhausted(RuntimeError):
    """Still 429/503 after every retry: the model's quota is used up."""


def render(review):
    """Comment body for one deliverable: criteria losing marks first, each
    with the reason and the fix; full-mark and not-judged rows folded away."""
    short, full, na = [], [], []
    for c in review["criteria"]:
        scored = c.get("points") is not None and c.get("max_points") is not None
        (na if c.get("status") == "na" else
         short if scored and c["points"] < c["max_points"] else full).append(c)

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
            icon = "🔴" if c["max_points"] - c["points"] >= 2 else "⚠️"
            out.append(f"**{icon} {c['name']}** — {pts(c)} → top is "
                       f"**{c.get('max_level') or 'top level'}** "
                       f"({c['max_points']:g})\n"
                       f"- **Why:** {c['why'].strip()}\n"
                       f"- **Fix:** {c.get('fix', '').strip() or 'n/a'}")
    else:
        out.append("### ✅ Nothing below the top level")
    if full:
        rows = "\n".join(f"- {c['name']} — {pts(c)}: {c['why'].strip()}" for c in full)
        out.append(f"<details><summary>✅ Full marks ({len(full)})</summary>"
                   f"\n\n{rows}\n\n</details>")
    if na:
        rows = "\n".join(f"- {c['name']}: {c['why'].strip()}" for c in na)
        out.append(f"<details><summary>➖ Not judged from the document "
                   f"({len(na)})</summary>\n\n{rows}\n\n</details>")
    if review.get("pr_note", "").strip():
        out.append(f"**This PR:** {review['pr_note'].strip()}")
    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--rubrics-dir", required=True)
    ap.add_argument("--map", default=".github/rubric-map.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fallback-model", default=FALLBACK_MODEL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.map, encoding="utf-8") as fh:
        mapping = json.load(fh)
    # Three dots: only the PR's own changes, not what landed on base since.
    rng = f"{args.base}...{args.head}"
    files = git("diff", "--name-only", "-M", rng).split()
    hits = [(p, r) for p, r in mapping.items() if not p.startswith("_")
            and any(f == p or f.startswith(p) for f in files)]
    if not hits:
        print(f"{MARKER}\nNo rubric-mapped documents changed in this pull request.")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        sys.exit("GEMINI_API_KEY is not set")

    sections = [MARKER, "## Rubric review"]
    used = set()
    for prefix, rubrics in hits:
        diff = git("diff", "-M", rng, "--", prefix)
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n... (diff truncated)"
        rubric = "\n\n---\n\n".join(
            open(os.path.join(args.rubrics_dir, r), encoding="utf-8").read().strip()
            for r in rubrics)
        prompt = PROMPT.format(rubric=rubric, diff=diff,
                               document=document_text(args.head, prefix))
        title = f"## `{prefix}` — {', '.join(r[:-3] for r in rubrics)}"
        if args.dry_run:
            sections.append(f"{title}\n\n```\n{prompt}\n```")
            continue
        raw = ""
        try:
            try:
                raw = call_gemini(args.model, api_key, prompt)
                used.add(args.model)
            except QuotaExhausted:
                print(f"{args.model} out of quota, trying {args.fallback_model}",
                      file=sys.stderr)
                raw = call_gemini(args.fallback_model, api_key, prompt)
                used.add(args.fallback_model)
            body = render(json.loads(raw))
        except RuntimeError as err:
            body = f"Review failed: {err}"
        except (ValueError, KeyError, TypeError) as err:
            # Schema-constrained output should always parse; show it if not.
            body = f"Review came back in an unexpected shape ({err}):\n\n```\n{raw[:4000]}\n```"
        sections.append(f"{title}\n\n{body}")

    models = ", ".join(f"`{m}`" for m in sorted(used)) or "no model (all calls failed)"
    sections.append(f"<sub>Reviewed by {models} against the rubrics in "
                    "`capstoneCEGJM/rubrics`. Advisory only; a TA may read it "
                    "differently.</sub>")
    print("\n\n".join(sections))


if __name__ == "__main__":
    main()
