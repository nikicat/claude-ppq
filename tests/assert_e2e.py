#!/usr/bin/env python3
"""Assert on a headless e2e run: no would-be permission prompts, expected text.

Usage: assert_e2e.py <claude-output.json> <perm-log.jsonl> <expect-substring> [forbid-substring]

- perm log must be empty (every command the model ran was pre-approved);
  otherwise the log — including the exact offending commands — is printed.
- the run's result text must contain expect-substring (case-insensitive)
  and must not contain forbid-substring, if given.
"""

import json
import pathlib
import sys


def main() -> int:
    out_file, log_file, expect = sys.argv[1], sys.argv[2], sys.argv[3]
    forbid = sys.argv[4] if len(sys.argv) > 4 else None

    ok = True
    log = pathlib.Path(log_file)
    if log.exists() and log.read_text(encoding="utf-8").strip():
        print("FAIL: commands escaped the allowed-tools grant (would have prompted):")
        for line in log.read_text(encoding="utf-8").splitlines():
            print("  " + line)
        ok = False

    d = json.load(open(out_file, encoding="utf-8"))  # Windows defaults to cp1252
    denials = d.get("permission_denials") or []
    if denials:
        print(f"FAIL: permission denials: {denials}")
        ok = False

    text = (d.get("result") or "").lower()
    if expect.lower() not in text:
        print(f"FAIL: expected {expect!r} in result; got: {text[:400]}")
        ok = False
    if forbid and forbid.lower() in text:
        print(f"FAIL: forbidden {forbid!r} present in result: {text[:400]}")
        ok = False

    if ok:
        print("OK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
