# Run the Shiny app using the active Python on PATH
Set-Location -Path $PSScriptRoot
python -m shiny run --port 50817 "$PSScriptRoot\app.py"
