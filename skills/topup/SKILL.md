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

## How to run it as an agent

1. **Check the balance first** — the user may not actually need a topup.
2. Creating an invoice is **free**; only paying it costs anything. Default $10 if
   the user didn't say an amount.
3. When you merely *suggest* topping up (low balance, 402), point the user at the
   skill — "run `/ppq:topup 10`" — never at a raw `uv run`/`!` shell command.
4. Create the invoice with `--no-wait` (the default mode polls up to 16 min and
   would hang the Bash tool).
5. **Relay the QR as text in your reply**: tool output is collapsed/cropped in
   the UI, but your reply renders in full — so copy the ASCII QR from the script
   output into a fenced code block, **character-for-character** (every `█▀▄` and
   space matters; don't trim, reflow, or "tidy" it). The script prints the
   expected `lines × chars` under the QR — check your copy matches before
   sending. The QR uses M-level error correction, so it survives a stray slip,
   but never reconstruct it from memory.
6. Below the QR give the `lightning:…` URI in its own fenced block (wallets
   accept it pasted), the invoice id, sats amount, and expiry. If the text QR
   won't scan or the user prefers a window, re-run with `--open` (pops the QR
   PNG in the image viewer; needs `$DISPLAY`/`$WAYLAND_DISPLAY`).
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
