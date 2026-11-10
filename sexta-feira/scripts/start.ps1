[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot)
$ErrorActionPreference='Stop'
$configFile=Join-Path ([IO.Path]::GetFullPath($RuntimeRoot)) 'config.json'
$config=Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
$env:SEXTA_DATA_DIR=$config.data_dir
$env:SEXTA_MODEL_DIR=$config.model_dir
$env:SEXTA_OFFLINE='1'
$env:SEXTA_PUBLIC_ORIGIN=$config.public_origin
Push-Location $config.project_dir
try { & $config.venv_python -m sexta_feira serve --host 127.0.0.1 --port $config.port --model small; if ($LASTEXITCODE -ne 0) { throw 'Application process failed.' } }
finally { Pop-Location }
