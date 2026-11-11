[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot,[ValidateSet('Install','Status','Disable')][string]$Action='Status')
$ErrorActionPreference='Stop'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$project=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$marker=Join-Path $runtime '.sexta-runtime'
if(-not(Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $project){throw 'Identified private runtime required'}
$directory=Join-Path $runtime 'sensors'
$script=Join-Path $directory 'collect-temperatures.ps1'
$exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$arguments='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$script+'"'
$taskName='SextaFeiraTemperatures'
$taskPath='\SextaFeira\'
$description='SEXTA-FEIRA owned read-only Windows temperature collector v1'
$task=Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction SilentlyContinue
if($task -and ($task.Description -ne $description -or @($task.Actions).Count -ne 1 -or $task.Actions.Execute -ne $exe -or $task.Actions.Arguments -ne $arguments)){throw 'Existing unrelated task preserved'}
if($Action -eq 'Status'){
 if($task){$task | Select-Object TaskName,State;Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath | Select-Object LastRunTime,LastTaskResult}else{Write-Output 'Temperature collector not installed'}
 exit 0
}
if($Action -eq 'Disable'){if($task){Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath | Out-Null};exit 0}
$principal=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required only to install the isolated collector'}
# A privileged task must not run a script replaceable by the unprivileged API.
$trusted=@('S-1-5-18','S-1-5-32-544',[Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
foreach($folder in @($runtime,$directory)){
 if(Test-Path -LiteralPath $folder){
  if((Get-Item -LiteralPath $folder).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse directory refused'}
  foreach($rule in (Get-Acl -LiteralPath $folder).Access){
   $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
   if($rule.AccessControlType -eq 'Allow' -and ($rule.FileSystemRights -band ([Security.AccessControl.FileSystemRights]::Write -bor [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor [Security.AccessControl.FileSystemRights]::TakeOwnership)) -and $sid -notin $trusted){throw 'Untrusted write access to collector parent refused'}
  }
 }
}
if(Test-Path -LiteralPath $directory){
 if(-not(Test-Path -LiteralPath (Join-Path $directory '.sexta-sensors'))){throw 'Existing unowned sensors directory preserved'}
 if($task.State -eq 'Running'){throw 'Collector running; retry after completion'}
}else{New-Item -ItemType Directory -Path $directory | Out-Null}
$acl=[Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @('S-1-5-18','S-1-5-32-544','S-1-5-19')){
 $rights=if($sid -eq 'S-1-5-19'){'ReadAndExecute'}else{'FullControl'}
 $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),$rights,'ContainerInherit,ObjectInherit','None','Allow'))
}
Set-Acl -LiteralPath $directory -AclObject $acl
if(Test-Path -LiteralPath $script){if((Get-Item -LiteralPath $script).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse script refused'}}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'collect-temperatures.ps1') -Destination $script -Force
'sexta-sensors-v1' | Set-Content -LiteralPath (Join-Path $directory '.sexta-sensors') -Encoding ASCII
# Reset explicit child ACLs too: inheritance alone does not remove an old write grant.
foreach($file in Get-ChildItem -LiteralPath $directory -Force){
 if($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected collector child refused'}
 $fileAcl=[Security.AccessControl.FileSecurity]::new()
 $fileAcl.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544','S-1-5-19')){
  $rights=if($sid -eq 'S-1-5-19'){'ReadAndExecute'}else{'FullControl'}
  $fileAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),$rights,'Allow'))
 }
 Set-Acl -LiteralPath $file.FullName -AclObject $fileAcl
}
$actionSpec=New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $directory
$boot=New-ScheduledTaskTrigger -AtStartup
$periodic=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 30) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Priority 7
$identity=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$scheduler=New-Object -ComObject Schedule.Service
$scheduler.Connect()
try{$null=$scheduler.GetFolder($taskPath.TrimEnd('\'))}catch{$null=$scheduler.GetFolder('\').CreateFolder('SextaFeira')}
Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Action $actionSpec -Trigger @($boot,$periodic) -Settings $settings -Principal $identity -Description $description -Force | Out-Null
Start-ScheduledTask -TaskName $taskName -TaskPath $taskPath
Write-Output 'Installed fixed read-only collector; API remains LocalService. No sensor driver installed.'
