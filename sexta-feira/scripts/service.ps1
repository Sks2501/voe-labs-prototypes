[CmdletBinding()]
param(
 [ValidateSet('Install','Start','Stop','Status','Uninstall')][string]$Action='Status',
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [string]$WinSWPath='',
 [ValidatePattern('^$|^[0-9a-fA-F]{64}$')][string]$WinSWSha256=''
)
$ErrorActionPreference='Stop'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot)
$project=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not (Test-Path -LiteralPath (Join-Path $runtime '.sexta-runtime'))) { throw 'Identified private runtime required.' }
if ((Get-Content -LiteralPath (Join-Path $runtime '.sexta-runtime') -Raw).Trim() -ne $project) { throw 'Runtime belongs to another checkout.' }
$configFile=Join-Path $runtime 'config.json'
$config=Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
$exe=Join-Path $runtime 'service\SextaFeira.exe'
$xml=Join-Path $runtime 'service\SextaFeira.xml'
$existing=Get-CimInstance Win32_Service -Filter "Name='SextaFeira'"
if ($existing -and $existing.PathName.Trim('"') -ne $exe) { throw 'Service name belongs to a different executable. No changes performed.' }
if ($Action -eq 'Status') { if ($existing) { $existing | Select-Object Name,State,StartMode,StartName } else { Write-Output 'SExtaFeira service is not installed.' }; exit 0 }
if ($Action -eq 'Install') {
  if ($existing) { throw 'Service already exists. Stop and follow the controlled update procedure; no replacement performed.' }
  . (Join-Path $PSScriptRoot "python.ps1")
  Assert-SextaServicePython -Executable $config.venv_python
  if (-not $WinSWPath -or -not $WinSWSha256) { throw 'Provide trusted WinSW 2.12.0 x64 executable and independently verified SHA256. No unverified binary will run.' }
  $actual=(Get-FileHash -LiteralPath $WinSWPath -Algorithm SHA256).Hash
  if ($actual -ne $WinSWSha256) { throw 'WinSW SHA256 mismatch.' }
  if ([Diagnostics.FileVersionInfo]::GetVersionInfo((Resolve-Path -LiteralPath $WinSWPath)).FileVersion -notmatch '^2\.12\.0') { throw 'Expected WinSW 2.12.0.' }
  Copy-Item -LiteralPath $WinSWPath -Destination $exe -ErrorAction Stop
  $escape={param($s) [Security.SecurityElement]::Escape([string]$s)}
  $pythonXml=& $escape $config.venv_python
  $runnerXml=& $escape (Join-Path $project 'scripts\service_runner.py')
  $configXml=& $escape $configFile
  $projectXml=& $escape $project
  $logsXml=& $escape (Join-Path $runtime 'logs')
  @"
<service>
 <id>SextaFeira</id><name>SEXTA-FEIRA Private GPT-2</name>
 <description>Private local OpenAI GPT-2 assistant. CPU only. No production service dependencies.</description>
 <executable>$pythonXml</executable>
 <startarguments>-B &quot;$runnerXml&quot; run &quot;$configXml&quot;</startarguments>
 <stopexecutable>$pythonXml</stopexecutable>
 <stoparguments>-B &quot;$runnerXml&quot; stop</stoparguments>
 <workingdirectory>$projectXml</workingdirectory>
 <serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>
 <startmode>Automatic</startmode><delayedAutoStart/>
 <stoptimeout>90 sec</stoptimeout>
 <onfailure action="restart" delay="5 sec"/><onfailure action="restart" delay="30 sec"/><onfailure action="none"/>
 <resetfailure>1 hour</resetfailure>
 <logpath>$logsXml</logpath><log mode="roll-by-size"><sizeThreshold>1024</sizeThreshold><keepFiles>3</keepFiles></log>
 <env name="PYTHONNOUSERSITE" value="1"/><env name="PYTHONDONTWRITEBYTECODE" value="1"/>
</service>
"@ | Set-Content -LiteralPath $xml -Encoding UTF8
  # Only this project's source receives service read permission; no parent ACLs change.
  & icacls.exe $project /grant '*S-1-5-19:(OI)(CI)RX' | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Source read ACL failed.' }
  & $exe install
  if ($LASTEXITCODE -ne 0) { throw 'WinSW install failed. No production service was changed.' }
  @{version='2.12.0';sha256=$actual;source='https://github.com/winsw/winsw/releases/tag/v2.12.0'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'service\wrapper-integrity.json') -Encoding UTF8
  Write-Output 'Installed as LocalService; not started. Run -Action Start, authenticated smoke, then record result.'
  exit 0
}
if (-not $existing) { throw 'Service not installed.' }
$receipt=Get-Content -LiteralPath (Join-Path $runtime 'service\wrapper-integrity.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -ne $receipt.sha256) { throw 'Installed wrapper integrity mismatch.' }
switch ($Action) {
 'Start' { & $exe start }
 'Stop' { & $exe stop }
 'Uninstall' { if ($existing.State -ne 'Stopped') { throw 'Stop SEXTA-FEIRA before uninstalling its service registration.' }; & $exe uninstall }
}
if ($LASTEXITCODE -ne 0) { throw "WinSW $Action failed." }
