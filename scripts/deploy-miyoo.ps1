param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost,
  [switch]$EnableButtonDiagnostic,
  [switch]$ReuseInstalledPlayerAssets,
  [string]$PlayerFontPath = ""
)

$ErrorActionPreference = "Stop"
$Destination = "/mnt/SDCARD/App/PocketStremio"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$playerBinary = Join-Path $root ".tmp\ffmpeg-2.4.14\ffplay"
$playerSysroot = Join-Path $root ".tmp\toolchain\mmiyoo\arm-buildroot-linux-gnueabihf\sysroot"
if (-not $PlayerFontPath) {
  $PlayerFontPath = Join-Path $root ".tmp\stremio-web\assets\fonts\PlusJakartaSans.ttf"
}
if (-not $ReuseInstalledPlayerAssets) {
  if (-not (Test-Path -LiteralPath $playerBinary -PathType Leaf)) {
    throw "Missing app-local FFplay candidate: $playerBinary"
  }
  if (-not (Test-Path -LiteralPath $PlayerFontPath -PathType Leaf)) {
    throw "Missing app-local subtitle font. Pass -PlayerFontPath with a licensed TTF: $PlayerFontPath"
  }
}
$sshOptions = @(
  "-tt",
  "-o", "MACs=+hmac-sha1",
  "-o", "StrictHostKeyChecking=accept-new"
)
$scpOptions = @(
  "-o", "MACs=+hmac-sha1",
  "-o", "StrictHostKeyChecking=accept-new"
)

function Invoke-Checked {
  param([string]$Command, [string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

$directories = @(
  $Destination,
  "$Destination/client",
  "$Destination/bin",
  "$Destination/config",
  "$Destination/logs",
  "$Destination/experiments",
  "$Destination/experiments/ffplay/bin",
  "$Destination/experiments/ffplay/lib",
  "$Destination/experiments/ffplay/fonts"
) -join " "
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, "mkdir -p $directories"))

$files = @(
  @{ Local = "app/config.json"; Remote = "config.json" },
  @{ Local = "app/launch.sh"; Remote = "launch.sh" },
  @{ Local = "app/playback-poc.sh"; Remote = "playback-poc.sh" },
  @{ Local = "client/miyoo/pocketstremio-ui.sh"; Remote = "client/pocketstremio-ui.sh" },
  @{ Local = "client/miyoo/pocketstremio-proxy.sh"; Remote = "client/pocketstremio-proxy.sh" },
  @{ Local = "client/miyoo/pocketstremio-resource-monitor.sh"; Remote = "client/pocketstremio-resource-monitor.sh" },
  @{ Local = "client/miyoo/bin/pocketstremio-selector"; Remote = "bin/pocketstremio-selector" },
  @{ Local = "client/miyoo/bin/pocketstremio-pause-monitor"; Remote = "bin/pocketstremio-pause-monitor" },
  @{ Local = "client/miyoo/bin/pocketstremio-playback-control"; Remote = "bin/pocketstremio-playback-control" },
  @{ Local = "client/miyoo/bin/pocketstremio-discovery"; Remote = "bin/pocketstremio-discovery" },
  @{ Local = "client/miyoo/pocketstremio.conf.example"; Remote = "config/pocketstremio.conf.example" },
  @{ Local = "experiments/button-diagnostic.sh"; Remote = "experiments/button-diagnostic.sh" },
  @{ Local = "client/miyoo/bin/pocketstremio-button-diagnostic"; Remote = "bin/pocketstremio-button-diagnostic" }
)
foreach ($file in $files) {
  $localPath = Join-Path $root $file.Local
  Invoke-Checked "scp" ($scpOptions + @($localPath, "${DeviceHost}:$Destination/$($file.Remote)"))
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
  @{ Name = "libuuid.so.1.3.0"; Remote = "libuuid.so.1" },
  @{ Name = "libts.so.0.10.4"; Remote = "libts.so.0" }
)
if (-not $ReuseInstalledPlayerAssets) {
  $runtimeFiles = @(
    @{ Local = $playerBinary; Remote = "experiments/ffplay/bin/ffplay" },
    @{ Local = (Join-Path $root "experiments\ffplay\fonts.conf"); Remote = "experiments/ffplay/fonts.conf" },
    @{ Local = $PlayerFontPath; Remote = "experiments/ffplay/fonts/PocketStremio.ttf" }
  )
  foreach ($runtimeFile in $runtimeFiles) {
    Invoke-Checked "scp" @($scpOptions + @($runtimeFile.Local, "${DeviceHost}:$Destination/$($runtimeFile.Remote)"))
  }
  foreach ($library in $libraries) {
    $source = Join-Path $playerSysroot "usr\lib\$($library.Name)"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
      $source = Join-Path $playerSysroot "lib\$($library.Name)"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
      throw "Missing app-local FFplay runtime library: $($library.Name)"
    }
    Invoke-Checked "scp" @($scpOptions + @($source, "${DeviceHost}:$Destination/experiments/ffplay/lib/$($library.Remote)"))
  }
}

$modeTargets = @(
  "$Destination/launch.sh",
  "$Destination/playback-poc.sh",
  "$Destination/client/pocketstremio-ui.sh",
  "$Destination/client/pocketstremio-proxy.sh",
  "$Destination/client/pocketstremio-resource-monitor.sh",
  "$Destination/bin/pocketstremio-selector",
  "$Destination/bin/pocketstremio-pause-monitor",
  "$Destination/bin/pocketstremio-playback-control",
  "$Destination/bin/pocketstremio-discovery",
  "$Destination/bin/pocketstremio-button-diagnostic",
  "$Destination/experiments/button-diagnostic.sh",
  "$Destination/experiments/ffplay/bin/ffplay"
) -join " "
$shellTargets = @(
  "$Destination/launch.sh",
  "$Destination/playback-poc.sh",
  "$Destination/client/pocketstremio-ui.sh",
  "$Destination/client/pocketstremio-proxy.sh",
  "$Destination/client/pocketstremio-resource-monitor.sh",
  "$Destination/experiments/button-diagnostic.sh"
) -join " "
$normalize = "for f in $shellTargets; do tr -d '\r' < `"`$f`" > `"`$f.lf`" && mv `"`$f.lf`" `"`$f`" || exit 1; done"
$playerVerifyTargets = @(
  "$Destination/experiments/ffplay/bin/ffplay",
  "$Destination/experiments/ffplay/fonts.conf",
  "$Destination/experiments/ffplay/fonts/PocketStremio.ttf"
) + ($libraries | ForEach-Object { "$Destination/experiments/ffplay/lib/$($_.Remote)" })
$playerVerify = "for f in $($playerVerifyTargets -join ' '); do test -s `"`$f`" || exit 1; done"
$verify = "$normalize && chmod +x $modeTargets && $playerVerify && /bin/sh -n $Destination/launch.sh && /bin/sh -n $Destination/client/pocketstremio-ui.sh && /bin/sh -n $Destination/client/pocketstremio-proxy.sh && /bin/sh -n $Destination/client/pocketstremio-resource-monitor.sh"
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, $verify))
if ($EnableButtonDiagnostic) {
  Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, "touch $Destination/config/button-diagnostic.mode"))
  Write-Output "Button diagnostic mode enabled for the next PocketStremio Apps launch"
}
if ($ReuseInstalledPlayerAssets) {
  Write-Output "PocketStremio deployed using verified existing app-local FFplay subtitle assets; live config and networking-provider state were preserved"
} else {
  Write-Output "PocketStremio deployed with app-local FFplay subtitle assets; live config and networking-provider state were preserved"
}
