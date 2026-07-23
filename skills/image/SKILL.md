---
name: image
description: Generate, edit, or upscale images with ppq.ai models — text-to-image from a prompt, image-to-image editing/retouching/restyling of an existing photo, deterministic upscaling, background removal, SVG generation. Use whenever the user wants to create or transform an image (via ppq, or when no other image backend is configured).
argument-hint: "[gen|edit|upscale|models] [prompt or file]"
---

# ppq.ai image generation

One self-contained script does everything (uv script — no install needed):

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/image/scripts/ppq_image.py"
uv run "$SCRIPT" gen "a red fox in fresh snow, golden hour" --ar 16:9 -o fox.png
uv run "$SCRIPT" edit photo.jpg "restyle as a 1940s film-noir portrait" -o noir.jpg
uv run "$SCRIPT" upscale small.jpg -o big.png
uv run "$SCRIPT" models [filter]        # live catalog + per-image prices (free call)
```

Key comes from `$PPQ_API_KEY` or `~/.config/ppq/api-key`. Every paid call prints
`cost $…` — always relay the cost to the user. HTTP 402 = balance empty → use the
`ppq:topup` skill.

## Picking a model

Prices surveyed 2026-07-23; re-check with `models` when it matters.

| Task | Model | $/image | Notes |
|---|---|---|---|
| t2i default | `nano-banana-2` | 0.092 | best prompt-following; honors `--ar` up to 21:9 |
| t2i cheap draft | `imagen4-fast` | 0.023 | good for iterating on prompts |
| t2i cheapest | `fast-sdxl` | 0.014 | lower quality |
| t2i alternatives | `seedream-4.5` 0.046, `flux-2-pro` 0.063, `imagen4-ultra` 0.069, `grok-imagine` 0.033 | | |
| edit default | `nano-banana-2-edit` | 0.092 | proven best at identity-preserving face edits |
| edit cheap | `qwen-image-2-edit` | 0.040 | also `seedream-4.5-edit` 0.066, `kling-v3-image-edit` 0.032; `flux-kontext-pro` 0.029 502'd on data-URI input when tested (2026-07) |
| upscale | `topaz-upscale` | 0.041 | deterministic; `aura-sr` 0.002 (cheap), `crystal-upscaler` 0.026 |
| background removal | `birefnet-v2` | 0.002 | use `edit` subcommand with any prompt |
| SVG / vector | `recraft-v4.1-svg` | 0.092 | raster: `recraft-v4.1` 0.046 |

Workflow for a "good" final image: iterate the prompt 1–2× on a cheap model, then
render the final on the good one. For a batch of edits, run several script
invocations in parallel (network-bound).

## Practical knowledge (learned the hard way)

- **Aspect ratio**: many models ignore `--ar`/size and return a square — crop
  yourself afterwards. `nano-banana-2` genuinely renders wide frames (21:9);
  `imagen4-*` honors 16:9.
- **Prompts for edits**: state what must be preserved explicitly, e.g. *"Keep the
  face, features, hair, expression and identity exactly the same. Photorealistic."*
  Illustrated/cartoon restyles redraw faces and lose likeness.
- **`--seed` is best-effort** — hosted models don't guarantee bit-exact repro even
  with a seed.
- Inputs are uploaded as data-URIs; the script downscales the long edge to 1536 px
  (`--max-px 0` to keep full size). Upscale inputs go lossless PNG, unresized.
- The script already retries 3× (a 200 can carry a provider error page instead of
  an image) and saves the returned bytes unrecompressed.
- Image-to-**video** models (`*-i2v`, `veo3-*`, `kling-*`…) also appear in the
  catalog but use the async `POST /v1/videos` endpoint — not this script.

## Raw API (if the script doesn't cover a parameter)

`POST https://api.ppq.ai/v1/images/generations` with bearer auth, JSON body:
`model`, `prompt`, plus optional `image_url` (data-URI or https), `aspect_ratio`
("16:9"), `resolution` ("1K"|"2K"|"4K"), `n` (1–4), `quality`, `negative_prompt`,
`output_format`, `seed`. Response: `{"data":[{"url": …}], "cost": …}`.
