#!/usr/bin/env python3
"""Validate every briefing against the Market Primer data contract and rebuild briefings/index.json.

Run from the repo root:  python3 scripts/validate.py
Exits 0 and prints "OK: N briefing(s) valid" when everything passes; otherwise lists every problem and exits 1.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFINGS = ROOT / "briefings"
INDEX = BRIEFINGS / "index.json"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIRECTIONS = {"up", "down", "flat"}
LENSES = ("you", "markets", "economy", "prices")
STORY_STRINGS = ("id", "category", "title", "tldr", "what_happened", "simple_explanation",
                 "analogy", "why", "watch")


def nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def check_briefing(path, data):
    errs = []

    def err(msg):
        errs.append(f"{path.name}: {msg}")

    if not isinstance(data, dict):
        err("top level must be a JSON object")
        return errs

    def need_str(obj, key, where):
        if not nonempty_str(obj.get(key)):
            err(f"{where}.{key} must be a non-empty string")
            return False
        return True

    def need_list(obj, key, where, lo, hi=None):
        v = obj.get(key)
        if not isinstance(v, list):
            err(f"{where}.{key} must be a list")
            return None
        if len(v) < lo or (hi is not None and len(v) > hi):
            rng = f"{lo}-{hi}" if hi is not None else f"at least {lo}"
            err(f"{where}.{key} has {len(v)} item(s); expected {rng}")
        return v

    # Top-level scalars
    for k in ("date", "session_label", "prepared_for", "headline", "mood", "mood_note", "big_picture"):
        need_str(data, k, "briefing")
    date = data.get("date")
    if isinstance(date, str):
        if not DATE_RE.match(date):
            err("date must be YYYY-MM-DD")
        elif path.stem != date:
            err(f"date '{date}' does not match file name '{path.stem}'")
    mood = data.get("mood")
    if isinstance(mood, str) and len(mood.split()) != 1:
        err("mood must be a single word")
    rm = data.get("reading_minutes")
    if isinstance(rm, bool) or not isinstance(rm, (int, float)) or rm <= 0:
        err("reading_minutes must be a positive number")

    # Simple string lists
    om = need_list(data, "one_minute", "briefing", 3, 5)
    if om is not None and not all(nonempty_str(x) for x in om):
        err("one_minute items must be non-empty strings")
    if "since_yesterday" in data:
        sy = need_list(data, "since_yesterday", "briefing", 1, 3)
        if sy is not None and not all(nonempty_str(x) for x in sy):
            err("since_yesterday items must be non-empty strings")

    # Chain
    chain = need_list(data, "chain", "briefing", 3, 6) or []
    for i, step in enumerate(chain):
        if not isinstance(step, dict):
            err(f"chain[{i}] must be an object")
            continue
        need_str(step, "label", f"chain[{i}]")
        need_str(step, "note", f"chain[{i}]")

    # Snapshot
    snap = data.get("snapshot")
    if not isinstance(snap, list):
        err("briefing.snapshot must be a list")
        snap = []
    for i, t in enumerate(snap):
        w = f"snapshot[{i}]"
        if not isinstance(t, dict):
            err(f"{w} must be an object")
            continue
        for k in ("name", "change", "what_it_is"):
            need_str(t, k, w)
        if not isinstance(t.get("value"), str):
            err(f"{w}.value must be a string (may be empty)")
        if t.get("direction") not in DIRECTIONS:
            err(f"{w}.direction must be one of up/down/flat")

    # Glossary
    glossary_terms = set()
    gl = data.get("glossary")
    if not isinstance(gl, list):
        err("briefing.glossary must be a list")
        gl = []
    for i, g in enumerate(gl):
        w = f"glossary[{i}]"
        if not isinstance(g, dict):
            err(f"{w} must be an object")
            continue
        if need_str(g, "term", w):
            glossary_terms.add(g["term"].strip().lower())
        need_str(g, "definition", w)
        need_str(g, "more", w)

    # Stories
    stories = need_list(data, "stories", "briefing", 3, 7) or []
    seen_ids = set()
    for i, s in enumerate(stories):
        w = f"stories[{i}]"
        if not isinstance(s, dict):
            err(f"{w} must be an object")
            continue
        for k in STORY_STRINGS:
            need_str(s, k, w)
        sid = s.get("id")
        if isinstance(sid, str):
            w = f"story '{sid}'"
            if not ID_RE.match(sid):
                err(f"{w}: id must be kebab-case")
            if sid in seen_ids:
                err(f"{w}: duplicate story id")
            seen_ids.add(sid)
        imp = s.get("implications")
        if not isinstance(imp, dict):
            err(f"{w}.implications must be an object")
        else:
            for lens in LENSES:
                need_str(imp, lens, f"{w}.implications")
        terms = s.get("terms")
        if not isinstance(terms, list) or not all(nonempty_str(t) for t in terms):
            err(f"{w}.terms must be a list of non-empty strings")
        else:
            for t in terms:
                if t.strip().lower() not in glossary_terms:
                    err(f"{w}: term '{t}' is missing from the glossary")
        ex = s.get("explainers")
        if not isinstance(ex, dict):
            err(f"{w}.explainers must be an object")
        else:
            need_str(ex, "like12", f"{w}.explainers")
            need_str(ex, "real_life", f"{w}.explainers")

    # Concept
    c = data.get("concept")
    if not isinstance(c, dict):
        err("briefing.concept must be an object")
    else:
        for k in ("term", "explanation", "example", "takeaway"):
            need_str(c, k, "concept")

    # Quiz
    quiz = need_list(data, "quiz", "briefing", 4, 7) or []
    for i, q in enumerate(quiz):
        w = f"quiz[{i}]"
        if not isinstance(q, dict):
            err(f"{w} must be an object")
            continue
        need_str(q, "q", w)
        need_str(q, "why", w)
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) != 4 or not all(nonempty_str(o) for o in opts):
            err(f"{w}.options must be a list of exactly 4 non-empty strings")
        a = q.get("answer")
        if isinstance(a, bool) or not isinstance(a, int) or not (0 <= a <= 3):
            err(f"{w}.answer must be an integer index 0-3")

    # Sources
    src = need_list(data, "sources", "briefing", 1) or []
    for i, so in enumerate(src):
        w = f"sources[{i}]"
        if not isinstance(so, dict):
            err(f"{w} must be an object")
            continue
        need_str(so, "title", w)
        url = so.get("url")
        if not (isinstance(url, str) and re.match(r"^https?://\S+$", url)):
            err(f"{w}.url must be an http(s) URL")

    return errs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    files = sorted(p for p in BRIEFINGS.glob("*.json") if p.name != "index.json")
    problems = []
    entries = []
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            problems.append(f"{p.name}: invalid JSON ({e})")
            continue
        errs = check_briefing(p, data)
        problems.extend(errs)
        if not errs:
            entries.append({
                "date": data["date"],
                "session_label": data["session_label"],
                "headline": data["headline"],
                "mood": data["mood"],
                "concept": data["concept"]["term"],
            })

    if problems:
        for msg in problems:
            print(f"ERROR {msg}")
        print(f"FAILED: {len(problems)} problem(s) found")
        return 1

    entries.sort(key=lambda e: e["date"], reverse=True)
    index = {
        "updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "briefings": entries,
    }
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(entries)} briefing(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
