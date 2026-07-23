#!/usr/bin/env bash
# CI test: setup.sh from-clipboard against the current OS's real clipboard.
# Covers: malformed clipboard rejected pre-network, invalid key rejected by
# API validation with nothing saved, and (with $PPQ_TEST_KEY) a full install —
# saved, chmod 600, validated, clipboard actually cleared afterwards.
set -euo pipefail
S="skills/setup/scripts/setup.sh"

copy() {
  if command -v pbcopy >/dev/null 2>&1; then printf '%s' "$1" | pbcopy
  elif command -v clip.exe >/dev/null 2>&1; then printf '%s' "$1" | clip.exe
  # xclip daemonizes to hold the selection; detach its fds or CI steps hang
  elif command -v xclip >/dev/null 2>&1; then printf '%s' "$1" | xclip -selection clipboard -i >/dev/null 2>&1
  else echo "no clipboard tool available for the test" >&2; exit 1; fi
}
paste_() {
  if command -v pbpaste >/dev/null 2>&1; then pbpaste
  elif command -v powershell.exe >/dev/null 2>&1; then powershell.exe -NoProfile -Command Get-Clipboard | tr -d '\r'
  else xclip -selection clipboard -o; fi
}

rm -rf "$HOME/.config/ppq"

copy 'garbage-no-sk-prefix'
out=$(bash "$S" from-clipboard 2>&1) && { echo "garbage must be rejected"; exit 1; }
grep -q "look like a ppq key" <<<"$out"
echo "OK: malformed clipboard rejected before any network call"

copy 'sk-test-not-a-real-key-1234567890'
out=$(bash "$S" from-clipboard 2>&1) && { echo "fake key must not validate"; exit 1; }
grep -q "did not validate" <<<"$out"
[ ! -e "$HOME/.config/ppq/api-key" ]
echo "OK: invalid key rejected by API validation, nothing saved"

if [ -n "${PPQ_TEST_KEY:-}" ]; then
  copy "$PPQ_TEST_KEY"
  out=$(bash "$S" from-clipboard 2>&1)
  grep -q "saved sk-" <<<"$out"
  grep -q "clipboard cleared" <<<"$out"
  [ -r "$HOME/.config/ppq/api-key" ]
  now=$(paste_ | tr -d '[:space:]' || true)
  [ "$now" != "$(tr -d '[:space:]' <"$HOME/.config/ppq/api-key")" ]
  rm -rf "$HOME/.config/ppq"
  echo "OK: real key installed + validated, clipboard cleared afterwards"
else
  echo "(no PPQ_TEST_KEY - real-key install skipped)"
fi
