---
name: topup
description: Top up the ppq.ai balance with Bitcoin Lightning (BOLT11 invoice + QR code + lightning link) or check the current balance/invoice status. Use when a ppq API call returns HTTP 402, the balance is low, or the user asks to top up ppq credits, check ppq balance, or make a lightning topup QR.
argument-hint: "[amount-usd | balance | status <id>]"
allowed-tools:
  - Bash(bash ${CLAUDE_SKILL_DIR}/scripts/topup *)
  - Bash(bash "${CLAUDE_SKILL_DIR}/scripts/topup" *)
  - Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/topup.py *)
  - Bash(uv run "${CLAUDE_SKILL_DIR}/scripts/topup.py" *)
  - Bash(pipx run ${CLAUDE_SKILL_DIR}/scripts/topup.py *)
  - Bash(pipx run "${CLAUDE_SKILL_DIR}/scripts/topup.py" *)
  - Skill(ppq:setup)
  - Skill(ppq:setup *)
---

# ppq.ai Lightning topup

One self-contained script behind a uv-locating launcher (no install needed):

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/topup balance                    # current balance in USD (free)
bash ${CLAUDE_SKILL_DIR}/scripts/topup 10 --no-wait               # create a 10 USD invoice, print QR + link, exit
bash ${CLAUDE_SKILL_DIR}/scripts/topup 10 --no-wait --png qr.png  # …and save the QR PNG (Read it → inline QR)
bash ${CLAUDE_SKILL_DIR}/scripts/topup 10 --no-wait --open        # …or pop the PNG in the OS image viewer
bash ${CLAUDE_SKILL_DIR}/scripts/topup status <id>                # one-shot check; exit 0 once paid
bash ${CLAUDE_SKILL_DIR}/scripts/topup status <id> --wait         # poll until paid/expired (background Bash)
```

Run these **exactly as shown** — one command, full script path, no `cd`, no
`SCRIPT=` variable, nothing chained, and the path copied byte-for-byte (keep
Windows backslashes as printed — rewriting separators or re-quoting breaks the
match). These exact shapes are pre-approved (`allowed-tools`) for as long as
this turn lasts; any other shape falls back to a normal permission prompt.
If a literal unsubstituted `${CLAUDE_SKILL_DIR}` appears above (older
harness), build the path from the "Base directory for this skill" header
instead — still the same launcher, never an improvised alternative.
**Keep the whole flow inside this one turn** —
need the user's input mid-flow (amount, confirmation)? Use the AskUserQuestion
tool (numbered choices): its answer returns as a tool result, the turn
continues, and the grant stays armed. A prose question ends the turn and
resets the grant.

Key: `$PPQ_API_KEY` → `~/.config/ppq/api-key` → `$OPENAI_API_KEY`. No key at
all → invoke the `ppq:setup` skill in this same turn (`Skill(ppq:setup)` is
pre-approved here); it installs a key or creates an anonymous account.

The launcher finds `uv` even when it's off the Bash tool's PATH (it checks a
login shell, then on Windows the registry-backed Path) and falls back to
`pipx`. **Never prefix `export PATH=…;` or any other setup command** —
chaining breaks the pre-approved match and triggers a permission prompt. If
the launcher reports that neither uv nor pipx exists, relay its install
hints; don't fall back to bare `python3` — the `qrcode` dependency won't be
installed.

## How to run it as an agent

1. **Check the balance first** — the user may not actually need a topup.
2. Creating an invoice is **free**; only paying it costs anything. Default
   10 USD if the user didn't say an amount.
3. When you merely *suggest* topping up (low balance, 402), point the user at the
   skill — "run `/ppq:topup 10`" — never at a raw `uv run`/`!` shell command.
4. Create the invoice with `--no-wait` (the default mode polls up to 16 min and
   would hang the Bash tool).
5. **Getting the QR scanned.** In a real terminal the collapsed Bash output
   already contains a scannable QR — tell the user to press **ctrl+o** (expand
   tool output). GUI surfaces (the Claude desktop app, editor panes) render
   that half-block QR with gaps between lines — unscannable. There, create
   the invoice with `--png qr.png` and then **Read the PNG file**: the image
   renders inline in the conversation, scannable straight off the screen.
   (`--open` also works — Windows/macOS/Linux image viewer — but it launches
   the OS default .png app, which may be a heavyweight editor like GIMP;
   prefer the inline Read.) Do NOT re-echo the QR into your reply as text by
   default: streaming ~2k block characters is slow. Last resort — only if the
   user asks for the QR as text — copy the ASCII QR into a fenced code block
   character-for-character (never reconstruct it; the script prints
   `lines × chars` to check the copy, and M-level error correction absorbs a
   stray slip).
6. In your reply give: the ctrl+o hint, the `lightning:…` URI in its own fenced
   block (wallets accept it pasted), the invoice id, sats amount, and expiry.
7. Then watch for payment with **exactly one background Bash call**:
   `status <id> --wait` — the script itself polls every few seconds until
   paid/expired (exit 0 = paid). Never hand-roll a `while` loop and never
   re-run one-shot `status` in a foreground loop: extra Bash calls mean
   permission prompts and, on Windows, a console window flashing at the user
   every time. One create call, one wait call, done. Report the outcome
   plainly: paid / expired / still pending.
8. On success the wait output already ends with `new balance: $…` — relay
   that; do **not** run a `balance` check afterwards. The background task
   completes on a fresh turn where the permission grant has expired, so any
   follow-up command prompts.

## Facts

- Lightning topups get a **~5% bonus**; invoices expire in **~15 minutes**.
- HTTP 402 from any ppq endpoint = balance exhausted; keep headroom ≈ 2× the
  planned spend for long runs.
- The response schema is undocumented — the script scans defensively for
  `lnbc…`/`lnurl…` strings and status fields, and dumps unknown schemas once.
- Other rails exist if the user prefers: `POST /topup/create/btc` (on-chain,
  60-min expiry), `/ltc`, `/lbtc`, `/xmr`; `GET /topup/payment-methods` lists
  limits. NWC auto-topup: `POST /nwc-auto-topup/connect` links a wallet for
  automatic refills.
- Balance: `POST https://api.ppq.ai/credits/balance` → `{"balance": <usd>}`.
