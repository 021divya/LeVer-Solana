$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:LANG = "C.UTF-8"
$env:LC_ALL = "C.UTF-8"

$env:OPENAI_BASE_URL = "http://localhost:11434/v1"
$env:LLM_BASE_URL = "http://localhost:11434/v1"
$env:OPENAI_API_KEY = "ollama"
$env:LLM_API_KEY = "ollama"

if (-not $env:LLM_MODEL) {
    $env:LLM_MODEL = "gemma4:e2b"
}
$env:LLM_REQUEST_TIMEOUT = "600"
$env:LLM_MAX_RETRIES = "2"
