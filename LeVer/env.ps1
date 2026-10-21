$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:LANG = "C.UTF-8"
$env:LC_ALL = "C.UTF-8"

$env:OPENAI_BASE_URL = "https://api.bluesminds.com/v1"
$env:LLM_BASE_URL = "https://api.bluesminds.com/v1"
$env:OPENAI_API_KEY = "sk-EaJ5PuFcpfXHD47RpntkfpYbvcHzLs519advUqfxW1XFho3p"
$env:LLM_API_KEY = "sk-EaJ5PuFcpfXHD47RpntkfpYbvcHzLs519advUqfxW1XFho3p"

if (-not $env:LLM_MODEL) {
    $env:LLM_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
}
$env:LLM_REQUEST_TIMEOUT = "600"
$env:LLM_MAX_RETRIES = "2"
