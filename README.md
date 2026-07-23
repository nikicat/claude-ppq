# ppq — a Claude Code plugin for ppq.ai

Three skills for working with [ppq.ai](https://ppq.ai) (pay-per-query AI gateway,
Bitcoin-friendly) from Claude Code:

| Skill | What it does |
|---|---|
| `ppq:image` | Text-to-image, image-to-image edit/restyle, upscaling, background removal via `POST /v1/images/generations`. Bundled `ppq_image.py` (uv script). |
| `ppq:claude-code` | Run Claude Code itself on ppq models (native Anthropic endpoint) — env var reference, bundled `claude-ppq` launcher, fish-function and settings.json recipes. |
| `ppq:topup` | Top up the balance over Bitcoin Lightning: BOLT11 invoice + terminal QR + `lightning:` link, status polling, balance check. Bundled `topup.py` (uv script). |

## Setup

1. Put your ppq API key in `~/.config/ppq/api-key` (`chmod 600`), or export
   `PPQ_API_KEY`.
2. Install the plugin:

```
# quick test (single session)
claude --plugin-dir /home/nb/src/ppq-skill

# permanent
/plugin marketplace add /home/nb/src/ppq-skill
/plugin install ppq@ppq
```

`uv` is required for the bundled scripts (they're PEP 723 inline-dependency
scripts — no venv or install step).

## Direct CLI use (no Claude needed)

```bash
uv run skills/image/scripts/ppq_image.py gen "a red fox in snow" --ar 16:9
uv run skills/image/scripts/ppq_image.py edit photo.jpg "film-noir portrait"
uv run skills/image/scripts/ppq_image.py models banana
uv run skills/topup/scripts/topup.py balance
uv run skills/topup/scripts/topup.py 10
skills/claude-code/scripts/claude-ppq -m moonshotai/kimi-k3
```
