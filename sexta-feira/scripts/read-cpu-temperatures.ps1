# Called only by the isolated SYSTEM collector after explicit driver authorization.
$ErrorActionPreference='Stop'
$manifestPath=Join-Path $PSScriptRoot 'libraries.json'
if((Get-Item -LiteralPath $manifestPath).Length -gt 32768){throw 'Library manifest too large'}
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if(@($manifest).Count -gt 64){throw 'Library inventory too large'}
foreach($entry in $manifest){
 if($entry.name -notmatch '^[a-zA-Z0-9._-]+\.dll$'){throw 'Library path refused'}
 $file=Join-Path $PSScriptRoot $entry.name
 if((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse library refused'}
 if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.sha256){throw 'Library integrity mismatch'}
}
$null=[Reflection.Assembly]::LoadFrom((Join-Path $PSScriptRoot 'LibreHardwareMonitorLib.dll'))
$computer=New-Object LibreHardwareMonitor.Hardware.Computer
$computer.IsCpuEnabled=$true
# All motherboard, memory-SPD, controllers, GPU, fan and power-control groups remain disabled.
try {
 $computer.Open()
 foreach($hardware in $computer.Hardware){
  if($hardware.HardwareType.ToString() -ne 'Cpu'){continue}
  $hardware.Update()
  foreach($sensor in $hardware.Sensors){
   if($sensor.SensorType.ToString() -ne 'Temperature' -or $null -eq $sensor.Value){continue}
   $value=[double]$sensor.Value
   if([double]::IsNaN($value) -or [double]::IsInfinity($value) -or $value -le 0 -or $value -ge 150){continue}
   if($sensor.Name -eq 'CPU Package'){@{component='cpu';kind='package';index=1;celsius=[Math]::Round($value,1)}}
   elseif($sensor.Name -match '^CPU Core #([1-9][0-9]?)$'){@{component='cpu';kind='core';index=[int]$Matches[1];celsius=[Math]::Round($value,1)}}
  }
 }
} finally {$computer.Close()}
