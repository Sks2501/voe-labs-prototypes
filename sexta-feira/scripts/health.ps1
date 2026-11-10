[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot)
$ErrorActionPreference='Stop'
$config=Get-Content -LiteralPath (Join-Path $RuntimeRoot 'config.json') -Raw | ConvertFrom-Json
$token=(Get-Content -LiteralPath (Join-Path $config.data_dir 'access.token') -Raw).Trim()
# Header is process memory only; do not enable PowerShell transcripts while handling secrets.
$response=Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/api/v1/health" -f $config.port) -Headers @{Authorization="Bearer $token"} -TimeoutSec 10
$token=$null
$response | ConvertTo-Json -Depth 5
