# ppq — a Claude Code plugin for ppq.ai

Three skills for working with [ppq.ai](https://ppq.ai) (pay-per-query AI gateway,
Bitcoin-friendly) from Claude Code:

| Skill | What it does |
|---|---|
| `ppq:setup` | Create an anonymous ppq account (`POST /accounts/create`) or install an existing key — without the key ever passing through the chat (clipboard/stdin ingestion, masked output). Bash+curl only. |
| `ppq:image` | Text-to-image, image-to-image edit/restyle, upscaling, background removal via `POST /v1/images/generations`. Bundled `ppq_image.py` (uv script). |
| `ppq:claude-code` | Run Claude Code itself on ppq models (native Anthropic endpoint) — env var reference, bundled `claude-ppq` launcher, fish-function and settings.json recipes. |
| `ppq:topup` | Top up the balance over Bitcoin Lightning: BOLT11 invoice + terminal QR + `lightning:` link, status polling, balance check. Bundled `topup.py` (uv script). |

## Setup

1. Get credentials — `/ppq:setup` handles both cases: installs an existing key
   to `~/.config/ppq/api-key` (chmod 600) via clipboard/stdin so it never
   touches the chat transcript, or creates a fresh anonymous account and hands
   off to `/ppq:topup` to fund it over Lightning. (Manual alternative: write
   the key file yourself, or export `PPQ_API_KEY`.)
2. Install the plugin (the repo is its own single-plugin marketplace):

```
/plugin marketplace add nikicat/claude-ppq
/plugin install ppq@ppq
```

For local development: `claude --plugin-dir /path/to/claude-ppq` (single
session), or `/plugin marketplace add /path/to/claude-ppq` (tracks your
working tree).

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
