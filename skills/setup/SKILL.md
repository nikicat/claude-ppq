---
name: setup
description: Set up ppq.ai credentials — create a new anonymous account (fully automated, funded over Lightning), install an existing API key WITHOUT it passing through the chat (clipboard/stdin), or inspect config status and balance. Use when no ppq key is configured, ppq returns 401, or the user wants a new ppq account or to store, replace, or check their key.
argument-hint: "[status | new | from-clipboard | from-stdin]"
allowed-tools:
  - Bash(bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh *)
  - Bash(bash "${CLAUDE_SKILL_DIR}/scripts/setup.sh" *)
  - Skill(ppq:topup)
  - Skill(ppq:topup *)
---

# ppq.ai setup (account + key)

One bash script, **no uv/python needed** (deliberate — setup may run on a fresh
machine before any tooling exists):

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh status            # config + balance overview (always masked)
bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh new               # create an anonymous account, save key + credit id
bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh from-clipboard    # install a key from the clipboard, then clear it
bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh from-stdin        # read a key from stdin (silent prompt on a TTY)
```

Run these **exactly as shown** — one command, full script path, no `cd`, no
`SCRIPT=` variable, nothing chained, and the path copied byte-for-byte (keep
Windows backslashes as printed — rewriting separators or re-quoting breaks the
match). These exact shapes are pre-approved (`allowed-tools`) for as long as
this turn lasts; any other shape falls back to a normal permission prompt.

Files: `~/.config/ppq/api-key` and `~/.config/ppq/credit-id`, both chmod 600.

## Secret hygiene — the rules that matter

- **Never ask the user to paste an API key into the chat.** Everything said in
  the conversation lands in transcript files on disk; the script's ingestion
  paths exist precisely so the key never enters model context.
- **Never `cat` or Read the key or credit-id files** (the Read tool counts —
  file contents land in the transcript), never put a key in a command's argv
  or an inline env assignment. `status` prints masked values by design — use
  it for any inspection; `test -r ~/.config/ppq/api-key` for a bare
  presence check.
- The `credit_id` is also a secret: it drives the `/keys` management API
  (`x-credit-id` header) and can mint new spending keys.

## Flows

**Keep the whole flow inside this one turn.** The `allowed-tools` grant dies
with the turn — ending your turn to ask something in prose means the next
script run hits a permission prompt. Need the user's input mid-flow? Use the
**AskUserQuestion tool** (numbered choices): the answer comes back as a tool
result, the turn continues, and the grant stays armed.

1. **Always run `status` first** — the user may already be configured; relay
   the masked overview.
2. **Unconfigured?** Ask with AskUserQuestion — options: install an existing
   key from the clipboard, create a new anonymous account, or type the key
   locally via from-stdin. Word the clipboard option so the user copies the
   key **before** selecting it (the dialog waits — e.g. "My key is on the
   clipboard now — install it").
3. **Existing key** (clipboard): after the answer, run `from-clipboard` — it
   validates the key against `/credits/balance` before saving, and clears the
   clipboard afterwards. Wrong clipboard contents? Re-ask with AskUserQuestion
   and retry — don't end the turn. No clipboard tooling: have the user run
   `! bash "${CLAUDE_SKILL_DIR}/scripts/setup.sh" from-stdin`
   themselves — the TTY prompt hides input and the key never reaches the
   conversation.
4. **New account**: run `new`. It POSTs `https://api.ppq.ai/accounts/create`
   (unauthenticated), saves both files, and prints masked ids. Always relay
   the no-recovery warning: anonymous account, the key IS the balance, back
   up `~/.config/ppq`. Then hand off to `ppq:topup` to fund it — invoke it
   in this same turn (`Skill(ppq:topup)` is pre-approved here); creation to
   funded balance is fully automated except the Lightning payment itself.
5. **Overwrite guard**: the script refuses `new`/`from-*` if a key file exists,
   because overwriting a funded account's key destroys the balance. Only add
   `--force` after the user explicitly confirmed they backed the old file up
   (AskUserQuestion, same turn).
6. Invalid keys are rejected before saving (validated with a free
   `/credits/balance` call), so a bad paste can't silently break a working
   config.
