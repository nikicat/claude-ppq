# Launch Claude Code on a ppq.ai model — native Windows (PowerShell) launcher.
# The sibling `claude-ppq` bash script is for POSIX shells; pasted into
# PowerShell it just opens in an editor. Use this instead:
#
#   powershell -ExecutionPolicy Bypass -File claude-ppq.ps1 [-m MODEL] [claude args...]
#   powershell -ExecutionPolicy Bypass -File claude-ppq.ps1 --models [filter]
#
# Env overrides: PPQ_API_KEY, PPQ_MODEL, PPQ_SMALL_MODEL, PPQ_AGENT_MODEL.
$ErrorActionPreference = 'Stop'
$rest = @($args)

# The model catalog is public — browsing needs no key.
if ($rest.Count -ge 1 -and $rest[0] -eq '--models') {
  $filter = if ($rest.Count -ge 2) { [string]$rest[1] } else { '' }
  $d = Invoke-RestMethod -Uri 'https://api.ppq.ai/v1/models'
  $rows = if ($d.PSObject.Properties['data']) { $d.data } else { $d }
  $rows | Where-Object { -not $filter -or $_.id -match [regex]::Escape($filter) } |
    Sort-Object id | ForEach-Object {
      $p = $_.pricing
      '{0,-40} in=${1}/1M out=${2}/1M ctx={3} priv={4}' -f `
        $_.id, $p.input_per_1M_tokens, $p.output_per_1M_tokens, $_.context_length, $_.privacyLevel
    }
  exit 0
}

# --- API key: $env:PPQ_API_KEY, else ~/.config/ppq/api-key -------------------
$key = $env:PPQ_API_KEY
$keyFile = Join-Path $env:USERPROFILE '.config/ppq/api-key'
if (-not $key -and (Test-Path $keyFile)) { $key = (Get-Content $keyFile -Raw).Trim() }
if (-not $key) {
  Write-Error "claude-ppq: no ppq.ai key. Put it in $keyFile or set `$env:PPQ_API_KEY."
  exit 1
}

$model = if ($env:PPQ_MODEL) { $env:PPQ_MODEL } else { 'moonshotai/kimi-k3' }
if ($rest.Count -ge 2 -and ($rest[0] -eq '-m' -or $rest[0] -eq '--model')) {
  $model = [string]$rest[1]
  $rest = if ($rest.Count -gt 2) { $rest[2..($rest.Count - 1)] } else { @() }
}
$small = if ($env:PPQ_SMALL_MODEL) { $env:PPQ_SMALL_MODEL } else { 'mistralai/mistral-nemo' }
$agent = if ($env:PPQ_AGENT_MODEL) { $env:PPQ_AGENT_MODEL } else { 'claude-sonnet-5' }

$env:ANTHROPIC_BASE_URL = 'https://api.ppq.ai'
$env:ANTHROPIC_AUTH_TOKEN = $key
$env:ANTHROPIC_MODEL = $model
$env:ANTHROPIC_SMALL_FAST_MODEL = $small
# Pin tier aliases so model-pinned subagents don't fall through to full-price Opus.
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $agent
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $agent
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $small
$env:DISABLE_PROMPT_CACHING = '1'

& claude @rest
exit $LASTEXITCODE
