# App-scoped interpreter discovery; never installs Python or changes external ACLs.
function Test-SextaPython {
  param([Parameter(Mandatory=$true)][string]$Executable,[string]$LauncherVersion='')
  $arguments=@()
  if ($LauncherVersion) { $arguments += $LauncherVersion }
  $arguments += @('-c','import sys; assert sys.maxsize>2**32; assert (3,11)<=sys.version_info[:2]<=(3,13); print(sys.executable)')
  try {
    $result=@(& $Executable @arguments 2>$null)
    if ($LASTEXITCODE -eq 0 -and $result.Count -eq 1 -and $result[0]) { return [IO.Path]::GetFullPath([string]$result[0]) }
  } catch { }
  return $null
}
function Find-SextaPython {
  param([string]$Requested='')
  if ($Requested) {
    $found=Test-SextaPython -Executable $Requested
    if ($found) { return $found }
    throw 'Selected Python must be version 3.11 through 3.13, 64-bit. Existing installation was not changed.'
  }
  $launcher=Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue
  if ($launcher) {
    foreach ($version in @('-3.11','-3.12','-3.13')) {
      $found=Test-SextaPython -Executable $launcher.Source -LauncherVersion $version
      if ($found) { return $found }
    }
  }
  $candidates=@(Get-Command python.exe,python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -Unique)
  foreach ($candidate in $candidates) {
    if ($candidate -match '(?i)[\\/]WindowsApps[\\/]') { continue }
    $found=Test-SextaPython -Executable $candidate
    if ($found) { return $found }
  }
  throw 'No supported 64-bit Python 3.11, 3.12 or 3.13 was found. Pass -Python with an existing interpreter; no global Python installation was changed.'
}
function Assert-SextaServicePython {
  param([Parameter(Mandatory=$true)][string]$Executable)
  $base=@(& $Executable -c 'import sys; print(sys.base_prefix)' 2>$null)
  if ($LASTEXITCODE -ne 0 -or $base.Count -ne 1) { throw 'Cannot inspect the base interpreter for the service.' }
  $basePath=[IO.Path]::GetFullPath([string]$base[0]).TrimEnd('\')
  if ($basePath -match '(?i)(^|[\\/])AppData([\\/]|$)') {
    throw 'Windows service requires an owner-installed machine-wide Python outside AppData. The selected venv uses per-user Python; no external ACL was changed. Install a separate machine-wide interpreter and prepare a new runtime.'
  }
  $profiles=@(Get-CimInstance Win32_UserProfile -ErrorAction Stop | Select-Object -ExpandProperty LocalPath)
  foreach ($profile in $profiles) {
    if (-not $profile) { continue }
    $profilePath=[IO.Path]::GetFullPath($profile).TrimEnd('\')
    if ($basePath.Equals($profilePath,[StringComparison]::OrdinalIgnoreCase) -or $basePath.StartsWith($profilePath+'\',[StringComparison]::OrdinalIgnoreCase)) {
      throw 'Windows service requires an owner-installed machine-wide Python outside user profiles. No profile or interpreter ACL was changed.'
    }
  }
}
