[CmdletBinding()]
param(
 [string]$RuntimeRoot='C:\SextaFeiraRuntime',
 [ValidateRange(1024,65535)][int]$Port=8765,
 [switch]$InstallService,
 [switch]$PrepareOnly
)
$ErrorActionPreference='Stop'
$project=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$pythonVersion='3.13.15'
$pythonUrl='https://api.nuget.org/v3-flatcontainer/python/3.13.15/python.3.13.15.nupkg'
$pythonHash='05357887df50d3153efc681bdf432c321d3e2f9ce5788f99f4515b27e8fda0ac'
$pythonSize=14391248L
$wrapperUrl='https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe'
$wrapperHash='05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da'
$wrapperSize=18243033L

function Assert-ContainedPath {
 param([string]$Candidate,[string]$Parent)
 $full=[IO.Path]::GetFullPath($Candidate)
 $prefix=[IO.Path]::GetFullPath($Parent).TrimEnd('\')+'\'
 if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Path escaped the dedicated bootstrap directory.'}
}
function Assert-NoReparseAncestor {
 param([string]$Target)
 $check=[IO.Path]::GetFullPath($Target)
 while($check){
  if(Test-Path -LiteralPath $check){
   $item=Get-Item -LiteralPath $check -Force
   if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Bootstrap requires local directories without junctions or symbolic links.'}
  }
  $parent=Split-Path -Parent $check
  if($parent -eq $check){break};$check=$parent
 }
}
function Assert-FileIntegrity {
 param([string]$Path,[string]$Sha256,[long]$Size)
 if(-not (Test-Path -LiteralPath $Path -PathType Leaf)){throw 'Required downloaded file is missing.'}
 if((Get-Item -LiteralPath $Path -Force).Length -ne $Size){throw 'Pinned download size mismatch; existing file preserved.'}
 if((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256){throw 'Pinned download SHA256 mismatch; existing file preserved.'}
}
function Get-PinnedDownload {
 param([string]$Url,[string]$Destination,[string]$Sha256,[long]$Size)
 Assert-NoReparseAncestor $Destination
 if(Test-Path -LiteralPath $Destination){Assert-FileIntegrity $Destination $Sha256 $Size;return}
 if(([uri]$Url).Scheme -ne 'https'){throw 'Only HTTPS downloads are permitted.'}
 $partial=$Destination+'.partial-'+[guid]::NewGuid().ToString('N')
 $response=$null;$downloadStream=$null;$output=$null
 try{
  $request=[Net.HttpWebRequest]::Create($Url)
  $request.Timeout=30000;$request.ReadWriteTimeout=30000;$request.AllowAutoRedirect=$true
  $request.UserAgent='SextaFeira-Provision/1.0'
  $response=$request.GetResponse()
  if($response.ResponseUri.Scheme -ne 'https'){throw 'Download redirected to an unencrypted endpoint.'}
  $downloadStream=$response.GetResponseStream()
  $output=[IO.File]::Open($partial,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  $buffer=New-Object byte[] 81920
  $total=0L
  while(($read=$downloadStream.Read($buffer,0,$buffer.Length)) -gt 0){
   $total+=$read;if($total -gt $Size){throw 'Download exceeded pinned size.'};$output.Write($buffer,0,$read)
  }
  $output.Dispose();$output=$null
  Assert-FileIntegrity $partial $Sha256 $Size
  # File.Move never replaces an existing destination.
  [IO.File]::Move($partial,$Destination)
 } finally{
  if($output){$output.Dispose()};if($downloadStream){$downloadStream.Dispose()};if($response){$response.Dispose()}
  if(Test-Path -LiteralPath $partial){Remove-Item -LiteralPath $partial -Force}
 }
}
function Assert-PythonReceipt {
 param([string]$Directory,[string]$ExpectedHash)
 $receiptPath=Join-Path $Directory '.sexta-python.json'
 if(-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)){throw 'Existing Python directory has no bootstrap receipt; it was preserved.'}
 $receipt=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
 if($receipt.package_sha256 -ne $ExpectedHash -or $receipt.version -ne '3.13.15'){throw 'Existing Python receipt does not match the pinned release.'}
 $files=@($receipt.files.PSObject.Properties)
 if($files.Count -lt 10){throw 'Python integrity receipt is incomplete.'}
 foreach($file in $files){
  $path=[IO.Path]::Combine($Directory,$file.Name);Assert-ContainedPath $path $Directory;Assert-NoReparseAncestor $path
  if(-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $file.Value){throw 'Extracted Python integrity mismatch; existing files preserved.'}
 }
}
function Prepare-Python {
 param([string]$Archive,[string]$Directory,[string]$Bootstrap)
 Assert-ContainedPath $Directory $Bootstrap
 if(Test-Path -LiteralPath $Directory){Assert-PythonReceipt $Directory $pythonHash;return}
 $staging=Join-Path $Bootstrap ('python-staging-'+[guid]::NewGuid().ToString('N'))
 Assert-ContainedPath $staging $Bootstrap
 [IO.Directory]::CreateDirectory($staging)|Out-Null
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $zip=[IO.Compression.ZipFile]::OpenRead($Archive)
 try{
  foreach($entry in $zip.Entries){
   $destination=[IO.Path]::Combine($staging,$entry.FullName)
   Assert-ContainedPath $destination $staging
   if((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000){throw 'Symlink entries are not permitted.'}
  }
 } finally{$zip.Dispose()}
 [IO.Compression.ZipFile]::ExtractToDirectory($Archive,$staging)
 $exe=Join-Path $staging 'tools\python.exe'
 & $exe -I -B -c 'import sys,venv,ensurepip; assert sys.version_info[:3]==(3,13,15); assert sys.maxsize>2**32'
 if($LASTEXITCODE -ne 0){throw 'Pinned Python failed its version/venv/ensurepip probe. Staging files preserved.'}
 $files=@{}
 foreach($file in Get-ChildItem -LiteralPath $staging -File -Recurse){$relative=$file.FullName.Substring($staging.Length+1);$files[$relative]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
 @{version='3.13.15';package_sha256=$pythonHash;source=$pythonUrl;files=$files}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $staging '.sexta-python.json') -Encoding UTF8
 # Both absolute paths were checked against this explicitly owned directory.
 Assert-ContainedPath $staging $Bootstrap;Assert-ContainedPath $Directory $Bootstrap
 [IO.Directory]::Move($staging,$Directory)
 Assert-PythonReceipt $Directory $pythonHash
}

if($env:OS -ne 'Windows_NT'){throw 'This bootstrap requires Windows.'}
if($runtime -eq [IO.Path]::GetPathRoot($runtime).TrimEnd('\') -or $runtime.StartsWith('\\')){throw 'Choose a dedicated local runtime directory, not a drive root or UNC path.'}
Assert-NoReparseAncestor $runtime
$profiles=@(Get-CimInstance Win32_UserProfile -ErrorAction Stop | Select-Object -ExpandProperty LocalPath)
foreach($userProfileDirectory in $profiles){
 if(-not $userProfileDirectory){continue};$profilePath=[IO.Path]::GetFullPath($userProfileDirectory).TrimEnd('\')
 if($runtime.Equals($profilePath,[StringComparison]::OrdinalIgnoreCase) -or $runtime.StartsWith($profilePath+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Portable service Python must be outside all user profiles. Choose C:\SextaFeiraRuntime or another dedicated local volume.'}
}
if($InstallService -and -not $PrepareOnly){
 $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Service provisioning requires an elevated PowerShell window. No service or global Python setting was changed.'}
}
$marker=Join-Path $runtime '.sexta-runtime'
if(Test-Path -LiteralPath $runtime){
 if(Test-Path -LiteralPath $marker){if((Get-Content -LiteralPath $marker -Raw).Trim() -ne $project){throw 'Runtime belongs to a different source checkout; existing files preserved.'}}
 elseif(@(Get-ChildItem -LiteralPath $runtime -Force).Count -gt 0){throw 'Destination is not an identified SEXTA-FEIRA runtime; choose a new empty directory.'}
}
$driveName=[IO.Path]::GetPathRoot($runtime).TrimEnd('\').TrimEnd(':')
$minimum=5GB;if($PrepareOnly){$minimum=256MB}
if((Get-PSDrive -Name $driveName).Free -lt $minimum){throw 'Insufficient free space on the selected runtime volume.'}
New-Item -ItemType Directory -Path $runtime -Force|Out-Null
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $runtime /inheritance:r /grant:r "*$($identity):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'|Out-Null
if($LASTEXITCODE -ne 0){throw 'Runtime ACL protection failed.'}
if(-not (Test-Path -LiteralPath $marker)){Set-Content -LiteralPath $marker -Value $project -Encoding UTF8}
$bootstrap=Join-Path $runtime '.bootstrap'
Assert-NoReparseAncestor $bootstrap
if((Test-Path -LiteralPath $bootstrap) -and -not (Test-Path -LiteralPath (Join-Path $bootstrap '.sexta-bootstrap')) -and @(Get-ChildItem -LiteralPath $bootstrap -Force).Count -gt 0){throw 'Unknown bootstrap directory preserved.'}
New-Item -ItemType Directory -Path $bootstrap -Force|Out-Null
$bootstrapMarker=Join-Path $bootstrap '.sexta-bootstrap'
if(Test-Path -LiteralPath $bootstrapMarker){if((Get-Content -LiteralPath $bootstrapMarker -Raw).Trim() -ne 'sexta-bootstrap-v1'){throw 'Bootstrap ownership marker mismatch.'}}
else{Set-Content -LiteralPath $bootstrapMarker -Value 'sexta-bootstrap-v1' -Encoding UTF8}
$lock=[IO.File]::Open((Join-Path $bootstrap 'provision.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$previousTls=[Net.ServicePointManager]::SecurityProtocol
$previousNoBytecode=$env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE='1'
$report=[ordered]@{started_utc=(Get-Date).ToUniversalTime().ToString('o');python='pending';installation='pending';service='not_requested';cloudflare='not_changed';python_version=$pythonVersion;python_sha256=$pythonHash}
try{
 [Net.ServicePointManager]::SecurityProtocol=$previousTls -bor [Net.SecurityProtocolType]::Tls12
 if($InstallService -and -not $PrepareOnly){
  $existing=Get-CimInstance Win32_Service -Filter "Name='SextaFeira'"
  if($existing){
   $expectedExe=Join-Path $runtime 'service\SextaFeira.exe'
   if($existing.PathName.Trim('"') -ne $expectedExe){throw 'Service name belongs to another executable; no service changed.'}
   if($existing.State -eq 'Stopped'){& (Join-Path $PSScriptRoot 'service.ps1') -Action Start -RuntimeRoot $runtime}
   elseif($existing.State -ne 'Running'){throw 'Existing service is transitioning. No restart was forced.'}
   & (Join-Path $PSScriptRoot 'health.ps1') -RuntimeRoot $runtime
   $report.service='existing_service_healthy';$report.installation='existing_preserved'
   Write-Output 'Existing SEXTA-FEIRA service is healthy; no dependency or source update performed.'
   return
  }
 }
 $archive=Join-Path $bootstrap 'python.3.13.15.nupkg'
 Write-Output 'Downloading/verifying official pinned Python package...'
 Get-PinnedDownload $pythonUrl $archive $pythonHash $pythonSize
 $portable=Join-Path $bootstrap 'python-3.13.15'
 Prepare-Python $archive $portable $bootstrap
 $pythonExe=Join-Path $portable 'tools\python.exe'
 $report.python='verified_ready'
 if($PrepareOnly){$report.installation='not_requested_prepare_only';Write-Output 'Pinned Python prepared. Dependencies, model and service were not installed.';return}
 & (Join-Path $PSScriptRoot 'install.ps1') -Python $pythonExe -RuntimeRoot $runtime -Port $Port
 $report.installation='installer_tests_passed'
 if($InstallService){
  $wrapper=Join-Path $bootstrap 'WinSW-2.12.0-x64.exe'
  Write-Output 'Downloading/verifying pinned WinSW wrapper...'
  Get-PinnedDownload $wrapperUrl $wrapper $wrapperHash $wrapperSize
  & (Join-Path $PSScriptRoot 'service.ps1') -Action Install -RuntimeRoot $runtime -WinSWPath $wrapper -WinSWSha256 $wrapperHash
  & (Join-Path $PSScriptRoot 'service.ps1') -Action Start -RuntimeRoot $runtime
  & (Join-Path $PSScriptRoot 'health.ps1') -RuntimeRoot $runtime
  $report.service='running_authenticated_health_passed'
 }
 $report.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
 Write-Output 'Provisioning finished. Inspect private installation and bootstrap reports. Cloudflare was not changed.'
} catch{$report.failure=$_.Exception.Message;throw}
finally{
 $report|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $bootstrap 'provision-report.json') -Encoding UTF8
 [Net.ServicePointManager]::SecurityProtocol=$previousTls
 $env:PYTHONDONTWRITEBYTECODE=$previousNoBytecode
 $lock.Dispose()
}
