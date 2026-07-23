---
name: topup
description: Top up the ppq.ai balance with Bitcoin Lightning (BOLT11 invoice + QR code + lightning link) or check the current balance/invoice status. Use when a ppq API call returns HTTP 402, the balance is low, or the user asks to top up ppq credits, check ppq balance, or make a lightning topup QR.
argument-hint: "[amount-usd | balance | status <id>]"
---

# ppq.ai Lightning topup

One self-contained script (uv script — no install needed):

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/topup/scripts/topup.py"
uv run "$SCRIPT" balance                 # current balance in USD (free)
uv run "$SCRIPT" 10 --no-wait            # create a $10 invoice, print QR + link, exit
uv run "$SCRIPT" 10 --no-wait --open     # …and pop the QR PNG in the image viewer
uv run "$SCRIPT" status <id>             # exit 0 once paid
uv run "$SCRIPT" --png qr.png 10         # save the QR PNG to a chosen path
```

Key: `$PPQ_API_KEY` → `~/.config/ppq/api-key` → `$OPENAI_API_KEY`.

**No `uv`?** If `uv run` fails with command-not-found, offer two fixes: install
uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or the distro package:
`pacman -S uv` / `brew install uv`), or run via `pipx run "$SCRIPT" …` (pipx
≥1.4.2 reads the same inline dependency metadata). Don't fall back to bare
`python3` — the only non-stdlib dependency (`qrcode`) won't be installed.

## How to run it as an agent

1. **Check the balance first** — the user may not actually need a topup.
2. Creating an invoice is **free**; only paying it costs anything. Default $10 if
   the user didn't say an amount.
3. When you merely *suggest* topping up (low balance, 402), point the user at the
   skill — "run `/ppq:topup 10`" — never at a raw `uv run`/`!` shell command.
4. Create the invoice with `--no-wait` (the default mode polls up to 16 min and
   would hang the Bash tool).
5. **Point the user at the tool output for the QR**: the full QR is already
   rendered in the collapsed Bash output — tell the user to press **ctrl+o**
   (expand tool output) and scan it right from the terminal. Do NOT re-echo the
   QR into your reply by default: streaming ~2k block characters is slow.
   Fallbacks, in order: `--open` (pops the QR PNG in the image viewer; needs
   `$DISPLAY`/`$WAYLAND_DISPLAY`), or — only if the user asks for the QR as
   text — copy the ASCII QR into a fenced code block character-for-character
   (never reconstruct it; the script prints `lines × chars` to check the copy,
   and M-level error correction absorbs a stray slip).
6. In your reply give: the ctrl+o hint, the `lightning:…` URI in its own fenced
   block (wallets accept it pasted), the invoice id, sats amount, and expiry.
7. Then poll `status <id>` in a background Bash loop (~10 s interval, stop at
   expiry) and report the outcome plainly: paid / expired / still pending.

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
