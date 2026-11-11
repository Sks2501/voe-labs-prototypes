[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [Parameter(Mandatory=$true)][string]$CloudflaredPath,
 [Parameter(Mandatory=$true)][string]$OriginCertificate,
 [ValidatePattern('^[a-z0-9-]+$')][string]$TunnelName='sexta-feira-private',
 [ValidatePattern('^[a-z0-9.-]+$')][string]$Hostname='sexta.teambike.online'
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$project=Split-Path -Parent $PSScriptRoot
if(-not (Test-Path (Join-Path $runtime '.sexta-runtime'))){throw 'Identified SEXTA-FEIRA runtime required.'}
if((Get-Content (Join-Path $runtime '.sexta-runtime') -Raw).Trim() -ne $project){throw 'Runtime source mismatch.'}
if(Get-Service SextaFeiraTunnel -ErrorAction SilentlyContinue){throw 'Existing private tunnel service requires controlled maintenance.'}
if(-not (Test-Path -LiteralPath $OriginCertificate)){throw 'An authorized existing Cloudflare origin certificate is required.'}
$configPath=Join-Path $runtime 'config.json'
$app=Get-Content -LiteralPath $configPath -Raw|ConvertFrom-Json
$token=(Get-Content -LiteralPath (Join-Path $app.data_dir 'access.token') -Raw).Trim()
$headers=@{Authorization="Bearer $token"}
$health=Invoke-RestMethod -Uri "http://127.0.0.1:$($app.port)/api/v1/health" -Headers $headers -TimeoutSec 10
try{Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$($app.port)/api/v1/health" -TimeoutSec 10|Out-Null;throw 'Unauthenticated API unexpectedly succeeded.'}
catch{if(-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401){throw}}
$directory=Join-Path $runtime 'cloudflare'
if(Test-Path -LiteralPath $directory){throw 'Existing tunnel artifacts preserved; inspect them before retrying.'}
New-Item -ItemType Directory -Path $directory|Out-Null
& icacls.exe $directory /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'|Out-Null
if($LASTEXITCODE){throw 'Tunnel directory ACL failed.'}
Copy-Item -LiteralPath $configPath -Destination (Join-Path $directory 'app-config.before.json')
$binary=Join-Path $directory 'cloudflared.exe'
Copy-Item -LiteralPath $CloudflaredPath -Destination $binary
$binaryHash=(Get-FileHash -LiteralPath $binary).Hash
if($binaryHash -ne (Get-FileHash -LiteralPath $CloudflaredPath).Hash){throw 'Cloudflare binary copy integrity mismatch.'}
$listText=& $binary tunnel --origincert $OriginCertificate list --output json
if($LASTEXITCODE){throw 'Authorized Cloudflare tunnel inventory failed.'}
$tunnels=($listText -join "`n")|ConvertFrom-Json
if(@($tunnels|Where-Object name -eq $TunnelName).Count){throw 'Tunnel name already exists; no existing tunnel was changed.'}
$credentials=Join-Path $directory 'credentials.json'
& $binary tunnel --origincert $OriginCertificate create --credentials-file $credentials $TunnelName
if($LASTEXITCODE){throw 'Private tunnel creation failed.'}
$credentialData=Get-Content -LiteralPath $credentials -Raw|ConvertFrom-Json
$tunnelId=[string]$credentialData.TunnelID
$credentialData=$null
if($tunnelId -notmatch '^[0-9a-f-]{36}$'){throw 'Unexpected tunnel identifier.'}
$tunnelConfig=Join-Path $directory 'config.yml'
@"
tunnel: $tunnelId
credentials-file: $($credentials.Replace('\','/'))
no-autoupdate: true
metrics: 127.0.0.1:0
loglevel: warn
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:$($app.port)
  - service: http_status:404
"@|Set-Content -LiteralPath $tunnelConfig -Encoding ASCII
& $binary tunnel --config $tunnelConfig ingress validate
if($LASTEXITCODE){throw 'Private ingress configuration is invalid.'}
$app|Add-Member -NotePropertyName public_origin -NotePropertyValue "https://$Hostname" -Force
$app|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $configPath -Encoding UTF8
& (Join-Path $PSScriptRoot 'service.ps1') -Action Stop -RuntimeRoot $runtime
& (Join-Path $PSScriptRoot 'service.ps1') -Action Start -RuntimeRoot $runtime
& (Join-Path $PSScriptRoot 'health.ps1') -RuntimeRoot $runtime
$wrapper=Join-Path $runtime 'service\SextaFeira.exe'
if((Get-FileHash $wrapper).Hash -ne '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da'){throw 'Verified WinSW wrapper required.'}
$serviceExe=Join-Path $runtime 'service\SextaFeiraTunnel.exe'
$serviceXml=Join-Path $runtime 'service\SextaFeiraTunnel.xml'
if((Test-Path $serviceExe) -or (Test-Path $serviceXml)){throw 'Existing service artifacts preserved.'}
Copy-Item -LiteralPath $wrapper -Destination $serviceExe
$logDirectory=Join-Path $runtime 'logs\tunnel'
New-Item -ItemType Directory -Path $logDirectory|Out-Null
$escape={param($s)[Security.SecurityElement]::Escape([string]$s)}
$binaryXml=& $escape $binary;$configXml=& $escape $tunnelConfig;$directoryXml=& $escape $directory;$logsXml=& $escape $logDirectory
@"
<service>
 <id>SextaFeiraTunnel</id><name>SEXTA-FEIRA Private Tunnel</name>
 <description>Dedicated authenticated assistant route. Independent of production Cloudflared.</description>
 <executable>$binaryXml</executable>
 <arguments>tunnel --config &quot;$configXml&quot; --no-autoupdate run</arguments>
 <workingdirectory>$directoryXml</workingdirectory>
 <serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>
 <depend>SextaFeira</depend><startmode>Automatic</startmode><delayedAutoStart/>
 <stoptimeout>30 sec</stoptimeout>
 <onfailure action="restart" delay="5 sec"/><onfailure action="restart" delay="30 sec"/><onfailure action="none"/>
 <resetfailure>1 hour</resetfailure>
 <logpath>$logsXml</logpath><log mode="roll-by-size"><sizeThreshold>1024</sizeThreshold><keepFiles>3</keepFiles></log>
</service>
"@|Set-Content -LiteralPath $serviceXml -Encoding UTF8
& $serviceExe install
if($LASTEXITCODE){throw 'Private tunnel service registration failed.'}
& $serviceExe start
if($LASTEXITCODE){throw 'Private tunnel service startup failed.'}
# No force flag: an existing DNS record is never overwritten.
& $binary tunnel --origincert $OriginCertificate route dns $tunnelId $Hostname
if($LASTEXITCODE){Stop-Service SextaFeiraTunnel;throw 'DNS publication failed; only the private tunnel was stopped.'}
@{hostname=$Hostname;tunnel=$tunnelId;cloudflared_sha256=$binaryHash;authentication='application_bearer_and_expiring_sessions';cloudflare_access='not_configured';production_tunnel='not_changed';published_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $directory 'publication.json') -Encoding UTF8
$token=$null;$headers=$null
Write-Output "Dedicated private route published: https://$Hostname. Verify HTTPS and authorization externally."
