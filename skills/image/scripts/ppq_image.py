#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "pillow"]
# ///
"""Generate, edit, or upscale images via the ppq.ai image API (pay-per-use).

    uv run ppq_image.py gen "a red fox in snow" [-m MODEL] [--ar 16:9] [-n 2] [-o out.png]
    uv run ppq_image.py edit photo.jpg "make it a noir portrait" [-m MODEL] [-o out.jpg]
    uv run ppq_image.py upscale small.jpg [-m topaz-upscale] [-o big.png]
    uv run ppq_image.py models [filter]        # live catalog + per-image price (free, no key)

Key: $PPQ_API_KEY, else ~/.config/ppq/api-key. Every paid call prints its cost.
Endpoint: POST https://api.ppq.ai/v1/images/generations
          {model, prompt, image_url?(data-uri), aspect_ratio?, resolution?, n?,
           negative_prompt?, quality?, seed?}  ->  {data: [{url|b64_json}], cost}
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time

import requests
from PIL import Image, UnidentifiedImageError

API = "https://api.ppq.ai/v1/images/generations"
MODELS_URL = "https://api.ppq.ai/v1/models?type=image"
UPSCALE_PROMPT = ("upscale to high resolution, enhance fine detail and sharpness, "
                  "preserve identity and content exactly")


def key_opt() -> str | None:
    k = os.environ.get("PPQ_API_KEY", "").strip()
    if k:
        return k
    p = os.path.expanduser("~/.config/ppq/api-key")
    if os.path.isfile(p):
        k = open(p).read().strip()
        if k:
            return k
    return None


def key() -> str:
    k = key_opt()
    if k:
        return k
    sys.exit("no ppq.ai key: set $PPQ_API_KEY or put it in ~/.config/ppq/api-key (chmod 600)")


def datauri(path: str, max_px: int, lossless: bool = False) -> str:
    """Encode an input image as a data URI; downscale the long edge to max_px (0 = keep)."""
    im = Image.open(path).convert("RGB")
    if max_px and max(im.size) > max_px:
        im.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    b = io.BytesIO()
    if lossless:  # upscalers should get a lossless, unresized source
        im.save(b, "PNG")
        mime = "image/png"
    else:
        im.save(b, "JPEG", quality=92)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(b.getvalue()).decode()


def call(payload: dict, tries: int = 3, timeout: int = 300) -> tuple[list[tuple[bytes, Image.Image]], object]:
    """POST once per attempt, download + decode every returned image.
    A 200 can still carry a non-image body (provider error page) -> retryable."""
    hdrs = {"Authorization": f"Bearer {key()}", "Content-Type": "application/json"}
    err = "no attempts"
    for i in range(tries):
        try:
            r = requests.post(API, headers=hdrs, json=payload, timeout=timeout)
            if r.status_code == 402:
                sys.exit("HTTP 402: insufficient ppq balance — top up (ppq:topup skill / topup.py)")
            if r.status_code == 200:
                j = r.json()
                out = []
                for item in j.get("data") or []:
                    raw = (base64.b64decode(item["b64_json"]) if item.get("b64_json")
                           else requests.get(item["url"], timeout=timeout).content)
                    im = Image.open(io.BytesIO(raw))
                    im.load()  # force full decode so a bad body fails here, not at save time
                    out.append((raw, im))
                if out:
                    return out, j.get("cost")
                err = f"200 but empty data[]: {json.dumps(j)[:200]}"
            else:
                err = f"http {r.status_code}: {r.text[:200]}"
        except (requests.RequestException, UnidentifiedImageError, KeyError, ValueError, OSError) as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
        if i < tries - 1:
            time.sleep(2 * (i + 1))
    sys.exit(f"failed after {tries} tries: {err}")


def slug(text: str, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "image"


def save_all(results: list[tuple[bytes, Image.Image]], out: str | None, base: str) -> None:
    for i, (raw, im) in enumerate(results):
        ext = (im.format or "png").lower().replace("jpeg", "jpg")
        if out and len(results) > 1:
            root, e = os.path.splitext(out)
            path = f"{root}-{i + 1}{e or '.' + ext}"
        else:
            path = out or (f"{base}.{ext}" if len(results) == 1 else f"{base}-{i + 1}.{ext}")
        with open(path, "wb") as f:  # raw bytes as delivered — no recompression
            f.write(raw)
        print(f"saved {path} ({im.size[0]}x{im.size[1]})")


def price_str(pricing: object) -> str:
    """base_price when present, else the min–max of any nested *price* fields."""
    if not isinstance(pricing, dict):
        return "?"
    if isinstance(pricing.get("base_price"), (int, float)):
        return f"${pricing['base_price']:.4f}"
    vals: list[float] = []
    stack: list[object] = [pricing]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(v, (int, float)) and "price" in k:
                    vals.append(float(v))
                elif isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    if not vals:
        return "?"
    lo, hi = min(vals), max(vals)
    return f"${lo:.4f}" + (f"–${hi:.4f}" if hi > lo else "")


def cmd_models(filt: str | None, as_json: bool) -> None:
    k = key_opt()  # the catalog is public — browse without a key, send one if present
    r = requests.get(MODELS_URL, headers={"Authorization": f"Bearer {k}"} if k else {}, timeout=60)
    r.raise_for_status()
    items = r.json().get("data", [])
    if filt:
        items = [m for m in items if filt.lower() in m["id"].lower()]
    if as_json:
        print(json.dumps(items, indent=2))
        return
    for m in items:
        video = " (video)" if re.search(r"-(i2v|v2v|r2v|t2v)$|video", m["id"]) else ""
        print(f"{m['id']:44} {price_str(m.get('pricing')):>18}{video}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="text-to-image")
    g.add_argument("prompt")
    g.add_argument("-m", "--model", default="nano-banana-2")
    g.add_argument("--ar", "--aspect-ratio", dest="ar", help='e.g. "1:1", "16:9", "21:9", "3:4"')
    g.add_argument("--resolution", help="1K, 2K or 4K (model-dependent)")
    g.add_argument("-n", type=int, help="number of images, 1-4 (model-dependent)")
    g.add_argument("--negative", help="negative prompt")
    g.add_argument("--quality", help="model-dependent quality tier, e.g. low/medium/high")
    g.add_argument("--seed", type=int, help="best-effort repro; hosted models aren't bit-exact")
    g.add_argument("-o", "--out")

    e = sub.add_parser("edit", help="image-to-image edit/restyle")
    e.add_argument("image")
    e.add_argument("prompt")
    e.add_argument("-m", "--model", default="nano-banana-2-edit")
    e.add_argument("--max-px", type=int, default=1536,
                   help="downscale input long edge before upload (0 = keep full size; default 1536)")
    e.add_argument("--ar", "--aspect-ratio", dest="ar")
    e.add_argument("--seed", type=int)
    e.add_argument("-o", "--out")

    u = sub.add_parser("upscale", help="deterministic upscale (no regeneration)")
    u.add_argument("image")
    u.add_argument("-m", "--model", default="topaz-upscale")
    u.add_argument("--prompt", default=UPSCALE_PROMPT)
    u.add_argument("-o", "--out")

    m = sub.add_parser("models", help="list image models + prices (free)")
    m.add_argument("filter", nargs="?")
    m.add_argument("--json", action="store_true")

    a = ap.parse_args()

    if a.cmd == "models":
        cmd_models(a.filter, a.json)
        return

    if a.cmd == "gen":
        payload = {"model": a.model, "prompt": a.prompt}
        for k_, v in (("aspect_ratio", a.ar), ("resolution", a.resolution), ("n", a.n),
                      ("negative_prompt", a.negative), ("quality", a.quality), ("seed", a.seed)):
            if v is not None:
                payload[k_] = v
        base = f"{slug(a.prompt)}-{a.model}"
    elif a.cmd == "edit":
        payload = {"model": a.model, "prompt": a.prompt, "image_url": datauri(a.image, a.max_px)}
        for k_, v in (("aspect_ratio", a.ar), ("seed", a.seed)):
            if v is not None:
                payload[k_] = v
        base = f"{os.path.splitext(os.path.basename(a.image))[0]}-{slug(a.prompt, 24)}"
    else:  # upscale
        payload = {"model": a.model, "prompt": a.prompt, "image_url": datauri(a.image, 0, lossless=True)}
        base = f"{os.path.splitext(os.path.basename(a.image))[0]}-upscaled"

    results, cost = call(payload)
    save_all(results, a.out, base)
    print(f"cost ${cost}")


if __name__ == "__main__":
    main()
