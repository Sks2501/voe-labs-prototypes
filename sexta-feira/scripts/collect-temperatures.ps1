# Fixed, read-only collector. No arguments, network, drivers, fan controls or commands from the API.
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$watch=[Diagnostics.Stopwatch]::StartNew()
$readings=@()
try {
 $zones=@(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -OperationTimeoutSec 5 | Select-Object -First 16)
 $index=0
 foreach($zone in $zones){
  $index++
  if($zone.Active -and $zone.CurrentTemperature -gt 2731 -and $zone.CurrentTemperature -lt 4231){
   $readings+=@{component='acpi';index=$index;celsius=[Math]::Round(([double]$zone.CurrentTemperature/10)-273.15,1)}
  }
 }
} catch {} # Access denied/unsupported is absence, never an invented value.
try {
 $disks=@(Get-PhysicalDisk | Select-Object -First 16)
 $index=0
 foreach($disk in $disks){
  $index++
  $counter=$disk | Get-StorageReliabilityCounter
  if($null -ne $counter.Temperature -and $counter.Temperature -gt 0 -and $counter.Temperature -lt 150){
   $readings+=@{component='storage';index=$index;celsius=[double]$counter.Temperature}
  }
 }
} catch {}
$snapshot=@{schema_version=1;scope='server';observed_at_utc=[DateTime]::UtcNow.ToString('o');readings=@($readings);collection_ms=$watch.ElapsedMilliseconds}
$target=Join-Path $PSScriptRoot 'temperatures.json'
$temporary=Join-Path $PSScriptRoot 'temperatures.tmp'
$json=$snapshot | ConvertTo-Json -Depth 4 -Compress
if([Text.Encoding]::UTF8.GetByteCount($json) -gt 65536){throw 'Snapshot size limit'}
[IO.File]::WriteAllText($temporary,$json,[Text.UTF8Encoding]::new($false))
if(Test-Path -LiteralPath $target){[IO.File]::Replace($temporary,$target,[NullString]::Value)}else{[IO.File]::Move($temporary,$target)}
