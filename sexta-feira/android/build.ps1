[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$SdkRoot,[Parameter(Mandatory=$true)][string]$JavaHome,
 [Parameter(Mandatory=$true)][string]$PrivateDirectory,[Parameter(Mandatory=$true)][string]$OutputRoot,
 [Parameter(Mandatory=$true)][string]$Python)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Security
$passwordFile=Join-Path $PrivateDirectory 'signing-password.dpapi'
$encrypted=[IO.File]::ReadAllBytes($passwordFile)
$plain=[Security.Cryptography.ProtectedData]::Unprotect($encrypted,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
try {
 $env:SEXTA_ANDROID_STOREPASS=[Text.Encoding]::UTF8.GetString($plain)
 & $Python -B (Join-Path $PSScriptRoot 'build.py') --sdk $SdkRoot --java $JavaHome --signing-key (Join-Path $PrivateDirectory 'sexta-feira-release.p12') --output $OutputRoot
 if($LASTEXITCODE){throw 'Android build failed'}
} finally {Remove-Item Env:\SEXTA_ANDROID_STOREPASS -ErrorAction SilentlyContinue;[Array]::Clear($plain,0,$plain.Length)}
