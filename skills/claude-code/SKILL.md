---
name: claude-code
description: Run or configure Claude Code against ppq.ai models (Kimi, DeepSeek, GLM, Qwen, Grok, Gemini, cheaper Claude…). Use when the user wants to launch Claude Code on a ppq model, create a claude-<model> launcher/fish function, pick or price ppq models, or troubleshoot a ppq-backed Claude Code setup.
argument-hint: "[model or task]"
allowed-tools:
  - Bash(${CLAUDE_SKILL_DIR}/scripts/claude-ppq *)
  - Bash("${CLAUDE_SKILL_DIR}/scripts/claude-ppq" *)
  - Bash(bash ${CLAUDE_SKILL_DIR}/scripts/claude-ppq *)
  - Bash(bash "${CLAUDE_SKILL_DIR}/scripts/claude-ppq" *)
  - Skill(ppq:setup)
  - Skill(ppq:setup *)
---

# Claude Code on ppq.ai

ppq.ai exposes a **native Anthropic `/v1/messages` endpoint**, so Claude Code
talks to it directly — no proxy. Everything is driven by env vars scoped to the
launch:

| Env var | Meaning | Typical value |
|---|---|---|
| `ANTHROPIC_BASE_URL` | point Claude Code at ppq | `https://api.ppq.ai` |
| `ANTHROPIC_AUTH_TOKEN` | ppq API key | from `~/.config/ppq/api-key` (none? → `ppq:setup`) |
| `ANTHROPIC_MODEL` | main model | e.g. `moonshotai/kimi-k3` |
| `ANTHROPIC_SMALL_FAST_MODEL` | background tasks (titles, summaries) | cheap, e.g. `mistralai/mistral-nemo` |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` `ANTHROPIC_DEFAULT_SONNET_MODEL` | what tier-pinned subagents resolve to | e.g. `claude-sonnet-5` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | haiku-pinned tasks | the cheap model |
| `DISABLE_PROMPT_CACHING` | `1` — most ppq upstreams don't do Anthropic prompt caching | `1` |

**Always pin the tier aliases**: otherwise model-pinned subagents (code-review,
etc.) fall through to real Opus via ppq at ~10.55/52.75 USD per 1M tokens.
(Prices in this file are written without dollar signs deliberately: a literal
dollar-digit sequence is a positional-argument placeholder in skill bodies
and gets mangled at render time.)

## Ready-made launcher

```bash
${CLAUDE_SKILL_DIR}/scripts/claude-ppq -m moonshotai/kimi-k3 [claude args…]
${CLAUDE_SKILL_DIR}/scripts/claude-ppq --models [filter]   # catalog with prices/ctx/privacy (no key needed)
```

**All model info comes from `--models`** — id, in/out price per 1M, context
length, privacy level. Never hand-roll `curl https://api.ppq.ai/…` plus
`python3`/`node` parsing: stock Windows has no python3 (a Store stub that
errors), hand-rolled commands aren't pre-approved (permission prompt every
time), and the API key must never appear inside a command line.

**Telling the user to launch it in their own terminal**: on POSIX shells give
the bash script path as-is; on Windows the user's terminal is
PowerShell/cmd, where the bash script just opens in a text editor — give
them instead:
`powershell -ExecutionPolicy Bypass -File "<skill dir>\scripts\claude-ppq.ps1" -m <model>`
(same flags, including `--models`).

Run these exactly as shown (one command, full path copied byte-for-byte —
keep Windows backslashes as printed — nothing chained) — these shapes are
pre-approved via `allowed-tools` for as long as this turn lasts.
Mid-flow questions (model choice, pricing tradeoffs): use the AskUserQuestion
tool, not a turn-ending prose question — its answer returns as a tool result
and the grant stays armed. No key configured → invoke `ppq:setup` in this
same turn (`Skill(ppq:setup)` is pre-approved here).

Defaults (all env-overridable): model `$PPQ_MODEL` → `moonshotai/kimi-k3`, small
`$PPQ_SMALL_MODEL` → `mistralai/mistral-nemo`, subagent tier `$PPQ_AGENT_MODEL` →
`claude-sonnet-5`. Suggest symlinking it onto `PATH` if the user wants it
permanently: `ln -s "${CLAUDE_SKILL_DIR}/scripts/claude-ppq" ~/.local/bin/`.

## Creating a per-model launcher

Match the user's shell and OS — check `$SHELL` first:

- **fish**: a function in `~/.config/fish/functions/claude-<name>.fish` with
  local `set -lx` exports so nothing leaks into the session; if one already
  exists (e.g. `claude-kimi.fish`), read it and copy its shape.
- **bash/zsh**: a function in the rc file, or a `claude-ppq` symlink on PATH
  plus `PPQ_MODEL=<model>`.
- **Windows**: a PowerShell function in `$PROFILE` wrapping
  `claude-ppq.ps1 -m <model>`.

Whatever the shell: key from `$PPQ_API_KEY` or `~/.config/ppq/api-key`, model
overridable via `$PPQ_MODEL`, and for a new model reconsider the small/agent
models' prices.

## Alternative: per-project settings.json

For a project that should always run on ppq, put the same vars in
`.claude/settings.json` instead of a launcher:

```json
{ "env": {
    "ANTHROPIC_BASE_URL": "https://api.ppq.ai",
    "ANTHROPIC_MODEL": "moonshotai/kimi-k3",
    "ANTHROPIC_SMALL_FAST_MODEL": "mistralai/mistral-nemo",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "mistralai/mistral-nemo",
    "DISABLE_PROMPT_CACHING": "1"
} }
```

Never write the API key into a settings file that might be committed —
`ANTHROPIC_AUTH_TOKEN` belongs in the environment / launcher / key file.

## Picking a model

Run `--models [filter]` — it prints price (in/out per 1M tokens), context
length, and `privacyLevel` (`zdr` zero-data-retention > `e2e` TEE > `anon`)
for every model, keyless. Check price and privacy before recommending. (Raw
API only if the launcher is unavailable: `GET https://api.ppq.ai/v1/models`,
keyless; pricing sits nested under `pricing.input_per_1M_tokens` /
`pricing.output_per_1M_tokens`.) Reference points surveyed 2026-07, in/out
USD per 1M tokens: kimi-k3 3.17/15.82 (anon), claude-sonnet-5 2.11/10.55,
claude-haiku-4.5 1.05/5.28, deepseek-v4-pro 0.46/0.92 (zdr), glm-5.2
0.82/2.57 (zdr, 1M ctx), qwen3-coder-30b 0.07/0.28 (zdr), grok-4.20
1.32/2.64 (2M ctx).

## Known quirks

- kimi-k3 latency can spike to minutes — don't assume a hang.
- Balance exhaustion mid-session returns **402** → `ppq:topup` skill; keep
  headroom ≈ 2× the planned spend.
- No Anthropic prompt caching on non-Claude upstreams — that's why
  `DISABLE_PROMPT_CACHING=1`; expect full-price input tokens each turn.
