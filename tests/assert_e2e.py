#!/usr/bin/env python3
"""Assert on a headless e2e run: permission escapes and expected output.

Usage:
  assert_e2e.py <claude-output.json> <perm-log.jsonl> --expect SUBSTR
                [--forbid SUBSTR] [--escapes-allowed SUBSTR] [--escapes-forbid SUBSTR]

Default: the perm log must be empty (every command was pre-approved); on
failure the log — including the exact offending commands — is printed.
With --escapes-allowed, escapes are permitted but every logged command must
contain that substring (e.g. the launcher path) — modelling follow-up turns
where the grant has expired and exactly one canonical command may prompt.
--escapes-forbid fails if any logged command contains the substring (e.g.
"curl"). The result text must contain --expect and not contain --forbid.
"""

import argparse
import json
import pathlib


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_json")
    ap.add_argument("perm_log")
    ap.add_argument("--expect", required=True)
    ap.add_argument("--forbid")
    ap.add_argument("--escapes-allowed")
    ap.add_argument("--escapes-forbid")
    args = ap.parse_args()

    ok = True
    log = pathlib.Path(args.perm_log)
    entries = []
    if log.exists():
        entries = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]

    if entries and not args.escapes_allowed:
        print("FAIL: commands escaped the allowed-tools grant (would have prompted):")
        for e in entries:
            print("  " + json.dumps(e))
        ok = False
    for e in entries:
        cmd = json.dumps(e.get("input") or {})
        if args.escapes_allowed and args.escapes_allowed not in cmd:
            print(f"FAIL: escape not matching {args.escapes_allowed!r}: {cmd[:300]}")
            ok = False
        if args.escapes_forbid and args.escapes_forbid in cmd:
            print(f"FAIL: forbidden escape {args.escapes_forbid!r}: {cmd[:300]}")
            ok = False

    d = json.load(open(args.output_json, encoding="utf-8"))  # Windows defaults to cp1252
    denials = d.get("permission_denials") or []
    if denials:
        print(f"FAIL: permission denials: {denials}")
        ok = False

    text = (d.get("result") or "").lower()
    if args.expect.lower() not in text:
        print(f"FAIL: expected {args.expect!r} in result; got: {text[:400]}")
        ok = False
    if args.forbid and args.forbid.lower() in text:
        print(f"FAIL: forbidden {args.forbid!r} present in result: {text[:400]}")
        ok = False

    if ok:
        print("OK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
