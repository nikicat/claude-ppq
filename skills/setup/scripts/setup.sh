#!/usr/bin/env bash
# ppq.ai account/key setup. Secret-safe by construction: the API key is never
# printed in full, never passed via argv, and never needs to enter a chat.
# Deliberately bash+curl only — no uv/python, so it works on a fresh machine.
#
#   setup.sh status                     # config + balance overview (masked)
#   setup.sh new [--force]              # create an anonymous account, save key + credit id
#   setup.sh from-clipboard [--force]   # install a key from the clipboard, then clear it
#   setup.sh from-stdin [--force]       # read a key from stdin (silent prompt on a TTY)
set -euo pipefail

API=https://api.ppq.ai
CFG="$HOME/.config/ppq"
KEY_FILE="$CFG/api-key"
CREDIT_FILE="$CFG/credit-id"

FORCE=0
args=()
for a in "$@"; do
  [[ $a == --force ]] && FORCE=1 || args+=("$a")
done
set -- "${args[@]:-}"

mask() {
  local s=${1:-}
  ((${#s} > 10)) && echo "${s:0:6}…${s: -4}" || echo "***"
}

perms() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null || echo '?'; }

balance_of() { # $1 = key -> prints USD balance, or nothing if the key doesn't validate
  curl -sf -X POST "$API/credits/balance" \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json" 2>/dev/null |
    sed -nE 's/.*"balance" *: *([0-9.eE+-]+).*/\1/p'
}

require_no_key() {
  [[ -e $KEY_FILE && $FORCE != 1 ]] || return 0
  local key bal
  key="$(tr -d '[:space:]' <"$KEY_FILE" 2>/dev/null || true)"
  bal="$(balance_of "$key" || true)"
  echo "refusing: $KEY_FILE already exists ($(mask "$key"), balance \$${bal:-?})." >&2
  echo "The key IS the balance — overwriting a funded account's key loses the money." >&2
  echo "Back the file up first, then re-run with --force." >&2
  exit 1
}

save_files() { # $1 = key, $2 = credit id (may be empty)
  umask 077
  mkdir -p "$CFG"
  printf '%s\n' "$1" >"$KEY_FILE"
  [[ -n ${2:-} ]] && printf '%s\n' "$2" >"$CREDIT_FILE"
  chmod 600 "$KEY_FILE" 2>/dev/null || true
}

install_key() { # $1 = candidate key: validate against the API, then persist
  local key=$1 bal
  if [[ $key != sk-* || ${#key} -lt 15 ]]; then
    echo "that doesn't look like a ppq key (sk-…): $(mask "$key")" >&2
    exit 1
  fi
  bal="$(balance_of "$key" || true)"
  if [[ -z $bal ]]; then
    echo "key $(mask "$key") did not validate against $API/credits/balance — not saved." >&2
    exit 1
  fi
  save_files "$key"
  echo "saved $(mask "$key") -> $KEY_FILE (chmod 600)  ·  balance \$$bal"
}

cmd_status() {
  if [[ -r $KEY_FILE ]]; then
    local key bal
    key="$(tr -d '[:space:]' <"$KEY_FILE")"
    bal="$(balance_of "$key" || true)"
    echo "key file : $KEY_FILE  ($(mask "$key"), mode $(perms "$KEY_FILE"))"
    echo "balance  : ${bal:+\$}${bal:-unreachable (bad key or network)}"
  else
    echo "key file : none ($KEY_FILE)"
  fi
  if [[ -r $CREDIT_FILE ]]; then
    echo "credit id: $(mask "$(tr -d '[:space:]' <"$CREDIT_FILE")")  ($CREDIT_FILE)"
  else
    echo "credit id: none"
  fi
  [[ -n ${PPQ_API_KEY:-} ]] && echo "env      : \$PPQ_API_KEY is set ($(mask "$PPQ_API_KEY")) — takes precedence"
  return 0
}

cmd_new() {
  require_no_key
  local resp key cid
  resp="$(curl -sf -X POST "$API/accounts/create" -H "Content-Type: application/json")"
  key="$(sed -nE 's/.*"api_key" *: *"([^"]+)".*/\1/p' <<<"$resp")"
  cid="$(sed -nE 's/.*"credit_id" *: *"([^"]+)".*/\1/p' <<<"$resp")"
  if [[ -z $key ]]; then
    echo "no api_key in the response: $resp" >&2
    exit 1
  fi
  save_files "$key" "$cid"
  echo "created anonymous ppq.ai account:"
  echo "  key       $(mask "$key")  -> $KEY_FILE (chmod 600)"
  echo "  credit id $(mask "$cid")  -> $CREDIT_FILE (chmod 600; grants key management — treat as secret)"
  echo "  balance   \$0 — fund it over Lightning (ppq:topup)"
  echo "⚠ anonymous account, NO recovery: back up $CFG — a lost key is a lost balance."
}

cmd_from_clipboard() {
  require_no_key
  local key clear_cmd
  if command -v wl-paste >/dev/null 2>&1; then
    key="$(wl-paste -n 2>/dev/null || true)"; clear_cmd="wl-copy --clear"
  elif command -v xclip >/dev/null 2>&1; then
    # the clearing xclip daemonizes to hold the selection; detach its fds so
    # callers (CI steps, tool harnesses) don't wait on the inherited pipes
    key="$(xclip -selection clipboard -o 2>/dev/null || true)"; clear_cmd="xclip -selection clipboard -i /dev/null >/dev/null 2>&1"
  elif command -v pbpaste >/dev/null 2>&1; then
    key="$(pbpaste)"; clear_cmd="pbcopy </dev/null"
  elif command -v powershell.exe >/dev/null 2>&1; then # Windows git-bash
    key="$(powershell.exe -NoProfile -Command Get-Clipboard 2>/dev/null | tr -d '\r' || true)"
    clear_cmd="powershell.exe -NoProfile -Command \"Set-Clipboard -Value ' '\""
  else
    echo "no clipboard tool found (wl-paste / xclip / pbpaste / powershell)" >&2
    exit 1
  fi
  install_key "$(tr -d '[:space:]' <<<"$key")"
  eval "$clear_cmd" 2>/dev/null && echo "(clipboard cleared)"
}

cmd_from_stdin() {
  require_no_key
  local key
  if [[ -t 0 ]]; then
    read -rs -p "paste ppq api key (input hidden): " key
    echo
  else
    key="$(cat)"
  fi
  install_key "$(tr -d '[:space:]' <<<"$key")"
}

case "${1:-status}" in
  status)         cmd_status ;;
  new)            cmd_new ;;
  from-clipboard) cmd_from_clipboard ;;
  from-stdin)     cmd_from_stdin ;;
  *) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
