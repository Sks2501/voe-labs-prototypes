[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot)
$ErrorActionPreference='Stop'
$configFile=Join-Path ([IO.Path]::GetFullPath($RuntimeRoot)) 'config.json'
$config=Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
$env:SEXTA_DATA_DIR=$config.data_dir
$env:SEXTA_MODEL_DIR=$config.model_dir
$env:SEXTA_OFFLINE='1'
$env:SEXTA_BACKEND=if($config.PSObject.Properties['backend']){$config.backend}else{'gpt2'}
foreach($pair in @(@('native_url','SEXTA_NATIVE_URL'),@('native_token_file','SEXTA_NATIVE_TOKEN_FILE'),@('history_after_id','SEXTA_HISTORY_AFTER_ID'))){
  if($config.PSObject.Properties[$pair[0]]){[Environment]::SetEnvironmentVariable($pair[1],[string]$config.($pair[0]),'Process')}
}
$env:SEXTA_PUBLIC_ORIGIN=$config.public_origin
Push-Location $config.project_dir
try { & $config.venv_python -m sexta_feira serve --host 127.0.0.1 --port $config.port --model small; if ($LASTEXITCODE -ne 0) { throw 'Application process failed.' } }
finally { Pop-Location }
