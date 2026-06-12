param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [string]$Title = "ngram-lab",
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

rsconnect deploy shiny . `
    --name $Name `
    --title $Title `
    --override-python-version $PythonVersion `
    --exclude ".github" `
    --exclude "_site" `
    --exclude "_shinylive_app" `
    --exclude ".shinylive" `
    --exclude "shinylive-cache" `
    --exclude "rsconnect-python" `
    --exclude "scripts/build_shinylive.py" `
    --exclude "__pycache__" `
    --exclude "*.pyc"
