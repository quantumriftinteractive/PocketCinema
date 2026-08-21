param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost,
  [switch]$Enable
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$candidate = Join-Path $root ".tmp\ffmpeg-2.4.14\ffplay"
$sysroot = Join-Path $root ".tmp\toolchain\mmiyoo\arm-buildroot-linux-gnueabihf\sysroot"
$destination = "/mnt/SDCARD/App/PocketStremio/experiments/ffplay"
$sshOptions = @(
  "-o", "MACs=+hmac-sha1",
  "-o", "StrictHostKeyChecking=accept-new"
)

if (-not (Test-Path -LiteralPath $candidate)) {
  throw "Missing candidate FFplay: $candidate"
}

$libraries = @(
  @{ Name = "libSDL-1.2.so.0.11.4"; Remote = "libSDL-1.2.so.0" },
  @{ Name = "libass.so.9.1.3"; Remote = "libass.so.9" },
  @{ Name = "libbz2.so.1.0.8"; Remote = "libbz2.so.1.0" },
  @{ Name = "libz.so.1.2.11"; Remote = "libz.so.1" },
  @{ Name = "libfontconfig.so.1.12.0"; Remote = "libfontconfig.so.1" },
  @{ Name = "libfreetype.so.6.17.4"; Remote = "libfreetype.so.6" },
  @{ Name = "libfribidi.so.0.4.0"; Remote = "libfribidi.so.0" },
  @{ Name = "libharfbuzz.so.0.30000.0"; Remote = "libharfbuzz.so.0" },
  @{ Name = "libglib-2.0.so.0.6800.4"; Remote = "libglib-2.0.so.0" },
  @{ Name = "libpcre.so.1.2.13"; Remote = "libpcre.so.1" },
  @{ Name = "libexpat.so.1.8.1"; Remote = "libexpat.so.1" },
  @{ Name = "libpng16.so.16.37.0"; Remote = "libpng16.so.16" },
  @{ Name = "libffi.so.8.1.0"; Remote = "libffi.so.8" },
  @{ Name = "libuuid.so.1.3.0"; Remote = "libuuid.so.1" }
  @{ Name = "libts.so.0.10.4"; Remote = "libts.so.0" }
)

function Invoke-Checked {
  param([string]$Command, [string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}

Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, "mkdir -p $destination/bin $destination/lib $destination/fonts"))
Invoke-Checked "scp" ($sshOptions + @($candidate, "${DeviceHost}:$destination/bin/ffplay"))
foreach ($library in $libraries) {
  $source = Join-Path $sysroot "usr\lib\$($library.Name)"
  if (-not (Test-Path -LiteralPath $source)) {
    $source = Join-Path $sysroot "lib\$($library.Name)"
  }
  if (-not (Test-Path -LiteralPath $source)) {
    throw "Missing runtime library: $source"
  }
  Invoke-Checked "scp" ($sshOptions + @($source, "${DeviceHost}:$destination/lib/$($library.Remote)"))
}

$launcher = Join-Path $root "experiments\ffplay-subtitle-experiment.sh"
Invoke-Checked "scp" ($sshOptions + @($launcher, "${DeviceHost}:/mnt/SDCARD/App/PocketStremio/experiments/ffplay-subtitle-experiment.sh"))
$fontConfig = Join-Path $root "experiments\ffplay\fonts.conf"
Invoke-Checked "scp" ($sshOptions + @($fontConfig, "${DeviceHost}:$destination/fonts.conf"))
$verify = "chmod +x /mnt/SDCARD/App/PocketStremio/experiments/ffplay/bin/ffplay /mnt/SDCARD/App/PocketStremio/experiments/ffplay-subtitle-experiment.sh"
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, $verify))
if ($Enable) {
  Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, "touch /mnt/SDCARD/App/PocketStremio/config/ffplay-subtitle-experiment.mode"))
  Write-Output "Subtitle FFplay experiment enabled for the next PocketStremio Apps launch"
}
Write-Output "App-local subtitle FFplay candidate deployed; Onion FFplay was not modified"
