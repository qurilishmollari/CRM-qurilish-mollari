$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$gitSafePath = $projectRoot.Replace('\', '/')

function Invoke-ProjectGit {
    param([string[]]$GitArguments)
    & git -C $projectRoot -c "safe.directory=$gitSafePath" @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed. Nothing further was attempted."
    }
}

$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project Python environment was not found.'
}

& $pythonPath (Join-Path $projectRoot 'manage.py') check
if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
& $pythonPath (Join-Path $projectRoot 'manage.py') makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Missing migration files. Publish stopped.' }

$branch = & git -C $projectRoot -c "safe.directory=$gitSafePath" branch --show-current
if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') {
    throw 'Switch to main before publishing.'
}
$remoteUrl = & git -C $projectRoot -c "safe.directory=$gitSafePath" remote get-url origin
if ($LASTEXITCODE -ne 0 -or $remoteUrl -notin @('https://github.com/qurilishmollari/CRM-qurilish-mollari.git', 'https://github.com/qurilishmollari/CRM-qurilish-mollari')) {
    throw 'Origin must point to the expected CRM repository.'
}

Invoke-ProjectGit -GitArguments @('add', '--', 'README.md', 'requirements.txt', 'Dockerfile', 'railway.json', 'config', 'crm/models.py', 'crm/views.py', 'crm/api', 'crm/reporting.py', 'crm/test_production_login.py', 'crm/test_accounts.py', 'crm/management/commands/setup_accounts.py', 'crm/migrations/0006_document_api_request_hash_document_api_request_id.py', 'docs', 'templates/crm/api_docs.html', 'static/crm/api_docs.css', 'static/crm/api_docs.js', 'tools/publish-api.ps1')
& git -C $projectRoot -c "safe.directory=$gitSafePath" diff --cached --quiet
$diffExitCode = $LASTEXITCODE
if ($diffExitCode -eq 1) {
    Invoke-ProjectGit -GitArguments @('-c', 'user.name=qurilishmollari', '-c', 'user.email=qurilishmollari@users.noreply.github.com', 'commit', '-m', 'Update mobile API and interactive documentation')
} elseif ($diffExitCode -ne 0) {
    throw 'Unable to inspect staged changes.'
}
Invoke-ProjectGit -GitArguments @('push', 'origin', 'main')
Write-Host 'GitHub push completed. Check the Railway deployment logs.' -ForegroundColor Green
