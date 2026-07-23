#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["qrcode[pil]"]
# ///
"""Top up the ppq.ai balance over Bitcoin Lightning and show a scannable QR.

Creates a BOLT11 topup invoice, renders a terminal QR (scan from a phone) plus a
clickable `lightning:` link (opens a desktop wallet), then polls until it settles
or expires — success exit 0, failure/timeout exit 1. Creating an invoice charges
nothing; only paying does. Lightning topups carry a ~5% bonus; invoices expire in
~15 minutes.

    uv run topup.py                  # $10 invoice (default), then poll to settle
    uv run topup.py 25               # $25 invoice
    uv run topup.py 25 --no-wait     # create + print, don't poll (for agents)
    uv run topup.py 25 --open        # also open the QR PNG in the image viewer
    uv run topup.py --png qr.png 25  # also save the QR as a PNG
    uv run topup.py status <id>          # one-shot status check, no polling
    uv run topup.py status <id> --wait   # poll until paid/expired (for agents)
    uv run topup.py balance              # current balance in USD (free)

Key: $PPQ_API_KEY, else ~/.config/ppq/api-key, else $OPENAI_API_KEY.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://api.ppq.ai"
DEFAULT_USD = 10.0
POLL_SECS = 4
MAX_WAIT_SECS = 16 * 60  # invoices expire ~15 min; give the settle a little slack

# undocumented status vocabulary — classify defensively (see _classify)
_PAID = {"paid", "settled", "complete", "completed", "confirmed", "success", "successful"}
_DEAD = {"expired", "cancelled", "canceled", "failed", "failure", "error", "void", "voided"}


def _key() -> str:
    k = os.environ.get("PPQ_API_KEY", "").strip()
    if k:
        return k
    p = os.path.expanduser("~/.config/ppq/api-key")
    if os.path.isfile(p):
        k = open(p).read().strip()
        if k:
            return k
    k = os.environ.get("OPENAI_API_KEY", "").strip()
    if k:
        return k
    raise SystemExit("no ppq.ai key: set $PPQ_API_KEY or put it in ~/.config/ppq/api-key (chmod 600)")


def _req(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {e.reason}\n{e.read().decode()[:1000]}") from None


def _scan(d: object, want: Callable[[object, str], bool]) -> str | None:
    """Depth-first search for the first string value matching `want(key, value)`."""
    stack: list[tuple[object, object]] = [(None, d)]
    while stack:
        k, cur = stack.pop()
        if isinstance(cur, str) and want(k, cur):
            return cur
        if isinstance(cur, dict):
            stack += list(cur.items())
        elif isinstance(cur, list):
            stack += [(k, v) for v in cur]
    return None


def _find_invoice(resp: dict) -> tuple[str | None, str | None]:
    """BOLT11 (lnbc…) and/or LNURL (lnurl…) anywhere in the response — ppq does not
    document the field name."""
    bolt11 = _scan(resp, lambda _k, v: v.lower().startswith("lnbc"))
    lnurl = _scan(resp, lambda _k, v: v.lower().startswith("lnurl"))
    return bolt11, lnurl


def _invoice_id(resp: dict) -> str | None:
    for k in ("invoice_id", "id", "credit_id", "payment_id", "topup_id", "charge_id"):
        v = resp.get(k)
        if isinstance(v, str | int):
            return str(v)
    return None


def _classify(resp: dict) -> tuple[str, str | None]:
    """(state, raw) where state ∈ {paid, dead, pending, unknown}. Handles boolean
    flags ({"paid": true}) and string status/state fields, top-level or nested."""
    for k in ("paid", "settled", "is_paid", "complete", "completed", "confirmed"):
        if resp.get(k) is True:
            return "paid", k

    def is_status_key(k: object, _v: str) -> bool:
        return isinstance(k, str) and ("status" in k.lower() or "state" in k.lower())

    raw = _scan(resp, is_status_key)
    if isinstance(raw, str):
        low = raw.lower()
        if low in _PAID:
            return "paid", raw
        if low in _DEAD:
            return "dead", raw
        return "pending", raw
    return "unknown", None


def _summary(resp: dict, amount_usd: float) -> str:
    parts = [f"invoice {resp.get('invoice_id', '?')}", f"${amount_usd:.2f}"]
    due = resp.get("amount_due")
    if isinstance(due, int | float) and due:
        parts.append(f"{round(due * 1e8):,} sats")
    exp = resp.get("expires_at")
    if isinstance(exp, int | float):
        left = int(exp - time.time())
        parts.append(f"expires in {left // 60}m{left % 60:02d}s" if left > 0 else "expired")
    return "  ·  ".join(parts)


def _show_qr(payload: str, png: str | None = None) -> None:
    import io
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M

    # M-level EC: the ASCII QR is often relayed by copying it as text (e.g. into an
    # agent's reply), and the extra redundancy absorbs a stray mis-copied character.
    qr = qrcode.QRCode(border=1, error_correction=ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)  # scannable directly in the terminal
    text = buf.getvalue()
    print(text, end="")
    lines = text.splitlines()
    width = max(map(len, lines))
    print(f"(QR: {len(lines)} lines × {width} chars — if relaying as text, copy verbatim)")
    if png:
        # full 4-module quiet zone — phone scanners need the margin the terminal QR skips
        big = qrcode.QRCode(border=4, error_correction=ERROR_CORRECT_L)
        big.add_data(payload)
        big.make(fit=True)
        with open(png, "wb") as f:
            big.make_image().save(f)
        print(f"QR saved to {png}")


def _link(uri: str, text: str) -> str:
    """OSC 8 terminal hyperlink: clickable where supported, plain text elsewhere."""
    return f"\033]8;;{uri}\033\\{text}\033]8;;\033\\"


def _open_file(path: str) -> bool:
    import shutil
    import subprocess

    startfile = getattr(os, "startfile", None)  # Windows-only
    if startfile is not None:
        startfile(os.path.abspath(path))
        return True
    for cmd in ("xdg-open", "open"):
        exe = shutil.which(cmd)
        if exe:
            subprocess.Popen([exe, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False


def _poll_until_terminal(invoice_id: str) -> int:
    """Poll status until paid/dead/timeout. Returns a process exit code."""
    print(
        f"\npolling every {POLL_SECS}s (Ctrl+C to stop; resume with "
        f"`topup.py status {invoice_id}`) …"
    )
    deadline = time.monotonic() + MAX_WAIT_SECS
    dumped = False
    while time.monotonic() < deadline:
        resp = _req(f"/topup/status/{invoice_id}")
        state, raw = _classify(resp)
        if state == "paid":
            print(f"\n✅ paid — balance topped up (status={raw!r}).")
            return 0
        if state == "dead":
            print(f"\n❌ {raw} — invoice will not settle.")
            return 1
        if state == "unknown" and not dumped:  # unrecognized schema — reveal it once
            print("\n" + json.dumps(resp, indent=2))
            dumped = True
        left = int(deadline - time.monotonic())
        print(f"\r  {raw or state} · {left // 60}m{left % 60:02d}s left  ", end="", flush=True)
        time.sleep(POLL_SECS)
    print("\n⌛ timed out — invoice expired unpaid.")
    return 1


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    no_wait = "--no-wait" in args
    open_qr = "--open" in args
    wait = "--wait" in args
    args = [a for a in args if a not in ("--no-wait", "--open", "--wait")]
    png = None
    if "--png" in args:
        i = args.index("--png")
        png = args[i + 1]
        del args[i : i + 2]

    if args and args[0] == "balance":
        resp = _req("/credits/balance", "POST", {})
        bal = resp.get("balance")
        print(f"${bal:.2f}" if isinstance(bal, int | float) else json.dumps(resp, indent=2))
        return 0
    if len(args) >= 2 and args[0] == "status":
        if wait:
            return _poll_until_terminal(args[1])
        resp = _req(f"/topup/status/{args[1]}")
        state, raw = _classify(resp)
        print(f"{state} (status={raw!r})")
        print(json.dumps(resp, indent=2))
        return 0 if state == "paid" else 1

    amount = float(args[0]) if args else DEFAULT_USD
    resp = _req("/topup/create/btc-lightning", "POST", {"amount": amount, "currency": "USD"})

    bolt11, lnurl = _find_invoice(resp)
    payload = bolt11 or lnurl
    if not payload:
        raise SystemExit(f"no lnbc…/lnurl… in the response:\n{json.dumps(resp, indent=2)}")
    print(_summary(resp, amount))
    if open_qr and not png:
        import tempfile

        png = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="ppq-topup-qr-").name
    # bech32 is case-insensitive; an uppercased BOLT11 packs into a smaller, easier QR
    _show_qr(payload.upper() if payload is bolt11 else payload, png)
    if open_qr and png and not _open_file(png):
        print("(no xdg-open/open found — open the QR PNG manually)")
    # clickable lightning: URI — opens a desktop wallet, and stays pasteable elsewhere
    uri = f"lightning:{payload}"
    print(f"\n⚡ {_link(uri, uri)}")

    invoice_id = _invoice_id(resp)
    if not invoice_id:
        print("\n(could not find an invoice-id field to poll — check the balance manually)")
        return 0
    if no_wait:
        print(f"\ninvoice id: {invoice_id}  (check: topup.py status {invoice_id})")
        return 0
    try:
        return _poll_until_terminal(invoice_id)
    except KeyboardInterrupt:
        print(f"\nstopped. Resume: topup.py status {invoice_id}")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
