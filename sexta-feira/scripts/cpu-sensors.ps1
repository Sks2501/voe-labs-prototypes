[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [ValidateSet('Prepare','Activate','Status','Disable')][string]$Action='Status',
 [switch]$AllowKernelDriver
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$project=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
if(-not(Test-Path -LiteralPath (Join-Path $runtime '.sexta-runtime')) -or (Get-Content (Join-Path $runtime '.sexta-runtime') -Raw).Trim() -ne $project){throw 'Identified private runtime required'}
$provider=Join-Path $runtime 'sensor-provider'
$marker=Join-Path $provider '.sexta-cpu-provider'
$enabledFile=Join-Path $provider 'enabled.json'
$driver=Get-CimInstance Win32_SystemDriver -Filter "Name='PawnIO'"
if($Action -eq 'Status'){
 @{provider_prepared=(Test-Path -LiteralPath $marker);driver_installed=($null -ne $driver);driver_state=$driver.State;enabled=if(Test-Path -LiteralPath $enabledFile){(Get-Content $enabledFile -Raw|ConvertFrom-Json).enabled}else{$false}}|ConvertTo-Json -Compress
 exit 0
}
if($Action -eq 'Disable'){
 if(-not(Test-Path -LiteralPath $marker)){throw 'Unowned provider preserved'}
 @{provider='lhm-0.9.6-pawnio-2.2.0';enabled=$false}|ConvertTo-Json|Set-Content $enabledFile -Encoding UTF8
 Write-Output 'CPU collection disabled; shared driver was not removed.'
 exit 0
}
$admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrative installer required'}
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
foreach($directory in @($runtime,$provider)){
 if(Test-Path -LiteralPath $directory){
  if((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse directory refused'}
  foreach($rule in (Get-Acl -LiteralPath $directory).Access){
   $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
   $writeMask=[Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor [Security.AccessControl.FileSystemRights]::TakeOwnership
   if($rule.AccessControlType -eq 'Allow' -and ($rule.FileSystemRights -band $writeMask) -and $sid -notin $trusted){throw 'Untrusted write access refused'}
  }
 }
}
if($Action -eq 'Prepare'){
 if(Test-Path -LiteralPath $provider){if(-not(Test-Path -LiteralPath $marker)){throw 'Existing unowned provider preserved'}}else{New-Item -ItemType Directory $provider|Out-Null}
 $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
 Set-Acl -LiteralPath $provider -AclObject $acl
 'sexta-cpu-provider-0.9.6-2.2.0'|Set-Content -LiteralPath $marker -Encoding ASCII
 $packages=Join-Path $provider 'packages';New-Item -ItemType Directory $packages -Force|Out-Null
 $assets=@(
  @{name='LibreHardwareMonitor-v0.9.6.zip';url='https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor.zip';hash='086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001'},
  @{name='PawnIO-2.2.0-setup.exe';url='https://github.com/namazso/PawnIO.Setup/releases/download/2.2.0/PawnIO_setup.exe';hash='1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032'}
 )
 foreach($asset in $assets){$destination=Join-Path $packages $asset.name;if(-not(Test-Path -LiteralPath $destination)){Invoke-WebRequest -UseBasicParsing -Uri $asset.url -OutFile $destination};if((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $asset.hash){throw 'Official asset digest mismatch'}}
 $installer=Join-Path $packages 'PawnIO-2.2.0-setup.exe'
 $signature=Get-AuthenticodeSignature -LiteralPath $installer
 if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -ne 'namazso.eu'){throw 'Official driver installer signature invalid'}
 $expanded=Join-Path $packages 'lhm-0.9.6'
 if(-not(Test-Path -LiteralPath $expanded)){Expand-Archive -LiteralPath (Join-Path $packages 'LibreHardwareMonitor-v0.9.6.zip') -DestinationPath $expanded}
 $inventory=@()
 foreach($library in Get-ChildItem -LiteralPath $expanded -File -Filter '*.dll'){
  Copy-Item -LiteralPath $library.FullName -Destination $provider -Force
  $inventory+=@{name=$library.Name;sha256=(Get-FileHash -LiteralPath $library.FullName -Algorithm SHA256).Hash}
 }
 if($inventory.Count -lt 2 -or $inventory.Count -gt 64){throw 'Unexpected library inventory'}
 $inventory|ConvertTo-Json|Set-Content (Join-Path $provider 'libraries.json') -Encoding UTF8
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'read-cpu-temperatures.ps1') -Destination $provider -Force
 # Assembly metadata inspection only. Prepare never opens hardware or runs the installer.
 $version=[Reflection.AssemblyName]::GetAssemblyName((Join-Path $provider 'LibreHardwareMonitorLib.dll')).Version
 if($version.ToString() -notmatch '^0\.9\.6\.'){throw 'Unexpected LHM assembly version'}
 if(-not(Test-Path -LiteralPath $enabledFile)){@{provider='lhm-0.9.6-pawnio-2.2.0';enabled=$false}|ConvertTo-Json|Set-Content $enabledFile -Encoding UTF8}
 Write-Output 'Prepared pinned libraries and signed installer. No driver installed or hardware opened.'
 exit 0
}
if(-not $AllowKernelDriver){throw 'Explicit kernel driver authorization is required: -AllowKernelDriver'}
if(-not(Test-Path -LiteralPath $marker)){throw 'Run Prepare first'}
$installer=Join-Path $provider 'packages\PawnIO-2.2.0-setup.exe'
if((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne '1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032'){throw 'Driver installer integrity mismatch'}
$signature=Get-AuthenticodeSignature -LiteralPath $installer
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -ne 'namazso.eu'){throw 'Driver installer signature invalid'}
$receiptFile=Join-Path $provider 'driver-installation.json'
if($driver -and -not(Test-Path -LiteralPath $receiptFile)){throw 'Pre-existing driver belongs to another installation; preserved'}
if(-not $driver){
 $result=Start-Process -FilePath $installer -ArgumentList @('-install','-silent') -WindowStyle Hidden -Wait -PassThru
 @{version='2.2.0';exit_code=$result.ExitCode;installed_at_utc=[DateTime]::UtcNow.ToString('o');installer_sha256='1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032'}|ConvertTo-Json|Set-Content $receiptFile -Encoding UTF8
 if($result.ExitCode -eq 3010){throw 'Driver installed but reboot required. Collection remains disabled; no reboot performed.'}
 if($result.ExitCode -ne 0){throw ('Driver installer failed with code '+$result.ExitCode+'. No security protections changed.')}
}
$driver=Get-CimInstance Win32_SystemDriver -Filter "Name='PawnIO'"
if(-not $driver){throw 'Driver installation not confirmed'}
@{provider='lhm-0.9.6-pawnio-2.2.0';enabled=$true;authorized_at_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content $enabledFile -Encoding UTF8
Write-Output 'Authorized CPU collector enabled. API permissions unchanged; no reboot performed.'
