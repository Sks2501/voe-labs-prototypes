[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$PrivateDirectory,[Parameter(Mandatory=$true)][string]$JavaHome)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Security
$directory=[IO.Path]::GetFullPath($PrivateDirectory)
if(-not(Test-Path -LiteralPath $directory)){New-Item -ItemType Directory -Path $directory|Out-Null}
$owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $directory '/inheritance:r' '/grant:r' "*${owner}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'|Out-Null
if($LASTEXITCODE){throw 'Private signing ACL failed'}
$key=Join-Path $directory 'sexta-feira-release.p12'
$passwordFile=Join-Path $directory 'signing-password.dpapi'
if((Test-Path $key) -or (Test-Path $passwordFile)){
 if(-not((Test-Path $key) -and (Test-Path $passwordFile))){throw 'Incomplete signing identity preserved. Restore it; do not regenerate.'}
 Write-Output 'Existing private signing identity preserved.'
 exit 0
}
$random=New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($random)
$password=[Convert]::ToBase64String($random)
$encrypted=[Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($password),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
try {
 $env:SEXTA_ANDROID_STOREPASS=$password
 & (Join-Path $JavaHome 'bin\keytool.exe') -genkeypair -keystore $key -storetype PKCS12 -alias sexta-feira -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=SEXTA-FEIRA Android, O=SEXTA-FEIRA, C=BR' -storepass:env SEXTA_ANDROID_STOREPASS -keypass:env SEXTA_ANDROID_STOREPASS -noprompt
 if($LASTEXITCODE){throw 'Signing identity creation failed'}
 [IO.File]::WriteAllBytes($passwordFile,$encrypted)
 Write-Output 'Private release identity created; password encrypted with Windows DPAPI.'
} finally {Remove-Item Env:\SEXTA_ANDROID_STOREPASS -ErrorAction SilentlyContinue;$password=$null;$random=$null}
