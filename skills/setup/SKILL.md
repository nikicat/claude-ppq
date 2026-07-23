---
name: setup
description: Set up ppq.ai credentials — create a new anonymous account (fully automated, funded over Lightning), install an existing API key WITHOUT it passing through the chat (clipboard/stdin), or inspect config status and balance. Use when no ppq key is configured, ppq returns 401, or the user wants a new ppq account or to store, replace, or check their key.
argument-hint: "[status | new | from-clipboard | from-stdin]"
---

# ppq.ai setup (account + key)

One bash script, **no uv/python needed** (deliberate — setup may run on a fresh
machine before any tooling exists):

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.sh"
bash "$SCRIPT" status            # config + balance overview (always masked)
bash "$SCRIPT" new               # create an anonymous account, save key + credit id
bash "$SCRIPT" from-clipboard    # install a key from the clipboard, then clear it
bash "$SCRIPT" from-stdin        # read a key from stdin (silent prompt on a TTY)
```

Files: `~/.config/ppq/api-key` and `~/.config/ppq/credit-id`, both chmod 600.

## Secret hygiene — the rules that matter

- **Never ask the user to paste an API key into the chat.** Everything said in
  the conversation lands in transcript files on disk; the script's ingestion
  paths exist precisely so the key never enters model context.
- **Never `cat` the key or credit-id files**, never put a key in a command's
  argv or an inline env assignment. `status` prints masked values by design —
  use it for any inspection.
- The `credit_id` is also a secret: it drives the `/keys` management API
  (`x-credit-id` header) and can mint new spending keys.

## Flows

1. **Always run `status` first** — the user may already be configured; relay
   the masked overview.
2. **New account** (user has no key): run `new`. It POSTs
   `https://api.ppq.ai/accounts/create` (unauthenticated), saves both files,
   and prints masked ids. Then hand off to `ppq:topup` to fund it — creation
   to funded balance is fully automated except the Lightning payment itself.
   Always relay the no-recovery warning: anonymous account, the key IS the
   balance, back up `~/.config/ppq`.
3. **Existing key**: tell the user to copy the key to the clipboard, then run
   `from-clipboard` — it validates the key against `/credits/balance` before
   saving, and clears the clipboard afterwards. Alternative (no clipboard
   tooling): have the user run
   `! bash "${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/setup.sh" from-stdin`
   themselves — the TTY prompt hides input and the key never reaches the
   conversation.
4. **Overwrite guard**: the script refuses `new`/`from-*` if a key file exists,
   because overwriting a funded account's key destroys the balance. Only add
   `--force` after the user explicitly confirms they backed the old file up.
5. Invalid keys are rejected before saving (validated with a free
   `/credits/balance` call), so a bad paste can't silently break a working
   config.
