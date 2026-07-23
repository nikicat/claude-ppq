# ppq — a Claude Code plugin for ppq.ai

Four skills for working with [ppq.ai](https://ppq.ai) (pay-per-query AI gateway,
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

## Permissions

Each skill pre-approves its own bundled script via `allowed-tools` in its
frontmatter, scoped to the exact script path (e.g.
`Bash(bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh *)`) — so invoking a skill
doesn't trigger a Bash permission prompt. Notes:

- Needs Claude Code ≥ 2.1.129 (`${CLAUDE_SKILL_DIR}` substitution); older
  versions simply fall back to the normal prompt.
- The grant lives exactly as long as the turn that invoked the skill, so the
  skills keep multi-step flows inside one turn: mid-flow questions ("which
  option?", "key copied?") use numbered-choice dialogs (the AskUserQuestion
  tool), whose answers return as tool results without ending the turn — the
  grant stays armed for the follow-up commands. A free-form reply on a later
  turn falls back to a normal prompt.
- Handoffs between ppq skills (setup → topup after account creation,
  image/topup → setup on a 401) are pre-approved via `Skill(...)` entries in
  the same grants, so they don't prompt when they happen within the turn.
- Want the scripts allowed permanently, prompts never? Add the equivalent
  allow rules with absolute paths to your `~/.claude/settings.json`.
- **Known limitation — Claude desktop app**: the desktop shell currently does
  not arm skill `allowed-tools` grants, so every command prompts there even
  though the identical flows run prompt-free in the CLI (verified continuously
  by this repo's e2e workflow). Tracked upstream:
  [anthropics/claude-code#80696](https://github.com/anthropics/claude-code/issues/80696).

## Direct CLI use (no Claude needed)

```bash
uv run skills/image/scripts/ppq_image.py gen "a red fox in snow" --ar 16:9
uv run skills/image/scripts/ppq_image.py edit photo.jpg "film-noir portrait"
uv run skills/image/scripts/ppq_image.py models banana
uv run skills/topup/scripts/topup.py balance
uv run skills/topup/scripts/topup.py 10
skills/claude-code/scripts/claude-ppq -m moonshotai/kimi-k3
```
