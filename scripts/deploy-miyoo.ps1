param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost,
  [switch]$EnableButtonDiagnostic,
  [switch]$ReuseInstalledPlayerAssets,
  [string]$PlayerFontPath = ""
)

$ErrorActionPreference = "Stop"
$Destination = "/mnt/SDCARD/App/PocketCinema"
$LegacyDestination = "/mnt/SDCARD/App/PocketStremio"
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
$deviceTarget = "root@$DeviceHost"
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

# This is a one-time development migration, not a runtime compatibility path.
# It copies only PocketCinema-owned state and never reads, moves, or alters the
# separate Tailscale application or its state.
$migration = @"
legacy='$LegacyDestination'
destination='$Destination'
if [ -d "`$legacy" ]; then
  mkdir -p "`$destination/config"
  if [ ! -e "`$destination/config/pocketcinema.conf" ] && [ -f "`$legacy/config/pocketstremio.conf" ]; then
    umask 077
    awk '
      /^LOCAL_PSS=/ { sub(/^LOCAL_PSS=/, "LOCAL_PCSERVER="); print; next }
      /^REMOTE_PSS=/ { sub(/^REMOTE_PSS=/, "REMOTE_PCSERVER="); print; next }
      /^POCKETSTREMIO_MATROSKA_SUBTITLES=/ { sub(/^POCKETSTREMIO_/, "POCKETCINEMA_"); print; next }
      { print }
    ' "`$legacy/config/pocketstremio.conf" > "`$destination/config/pocketcinema.conf.tmp" &&
      mv "`$destination/config/pocketcinema.conf.tmp" "`$destination/config/pocketcinema.conf"
  fi
  if [ ! -e "`$destination/config/last-play.json" ] && [ -f "`$legacy/config/last-play.json" ]; then
    cp -p "`$legacy/config/last-play.json" "`$destination/config/last-play.json.tmp" &&
      mv "`$destination/config/last-play.json.tmp" "`$destination/config/last-play.json"
  fi
fi
"@
Invoke-Checked "ssh" ($sshOptions + @($deviceTarget, $migration))

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
Invoke-Checked "ssh" ($sshOptions + @($deviceTarget, "mkdir -p $directories"))

if ($ReuseInstalledPlayerAssets) {
  $playerMigration = "legacy='$LegacyDestination'; destination='$Destination'; if [ ! -e `"`$destination/experiments/ffplay/bin/ffplay`" ] && [ -d `"`$legacy/experiments/ffplay`" ]; then cp -pR `"`$legacy/experiments/ffplay/.`" `"`$destination/experiments/ffplay/`"; fi; if [ ! -e `"`$destination/experiments/ffplay/fonts/PocketCinema.ttf`" ] && [ -f `"`$destination/experiments/ffplay/fonts/PocketStremio.ttf`" ]; then mv `"`$destination/experiments/ffplay/fonts/PocketStremio.ttf`" `"`$destination/experiments/ffplay/fonts/PocketCinema.ttf`"; fi; if [ -f `"`$destination/experiments/ffplay/fonts.conf`" ]; then sed 's|/mnt/SDCARD/App/PocketStremio|/mnt/SDCARD/App/PocketCinema|g; s|pocketstremio-fontconfig-cache|pocketcinema-fontconfig-cache|g' `"`$destination/experiments/ffplay/fonts.conf`" > `"`$destination/experiments/ffplay/fonts.conf.tmp`" && mv `"`$destination/experiments/ffplay/fonts.conf.tmp`" `"`$destination/experiments/ffplay/fonts.conf`"; fi"
  Invoke-Checked "ssh" ($sshOptions + @($deviceTarget, $playerMigration))
}

$files = @(
  @{ Local = "app/config.json"; Remote = "config.json" },
  @{ Local = "app/icon.png"; Remote = "icon.png" },
  @{ Local = "app/launch.sh"; Remote = "launch.sh" },
  @{ Local = "app/playback-poc.sh"; Remote = "playback-poc.sh" },
  @{ Local = "client/miyoo/pocketcinema-ui.sh"; Remote = "client/pocketcinema-ui.sh" },
  @{ Local = "client/miyoo/pocketcinema-proxy.sh"; Remote = "client/pocketcinema-proxy.sh" },
  @{ Local = "client/miyoo/pocketcinema-connection.sh"; Remote = "client/pocketcinema-connection.sh" },
  @{ Local = "client/miyoo/pocketcinema-resource-monitor.sh"; Remote = "client/pocketcinema-resource-monitor.sh" },
  @{ Local = "client/miyoo/bin/pocketcinema-selector"; Remote = "bin/pocketcinema-selector" },
  @{ Local = "client/miyoo/bin/pocketcinema-pause-monitor"; Remote = "bin/pocketcinema-pause-monitor" },
  @{ Local = "client/miyoo/bin/pocketcinema-playback-control"; Remote = "bin/pocketcinema-playback-control" },
  @{ Local = "client/miyoo/bin/pocketcinema-discovery"; Remote = "bin/pocketcinema-discovery" },
  @{ Local = "client/miyoo/pocketcinema.conf.example"; Remote = "config/pocketcinema.conf.example" },
  @{ Local = "experiments/button-diagnostic.sh"; Remote = "experiments/button-diagnostic.sh" },
  @{ Local = "client/miyoo/bin/pocketcinema-button-diagnostic"; Remote = "bin/pocketcinema-button-diagnostic" }
)
foreach ($file in $files) {
  $localPath = Join-Path $root $file.Local
  Invoke-Checked "scp" ($scpOptions + @($localPath, "${deviceTarget}:$Destination/$($file.Remote)"))
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
    @{ Local = $PlayerFontPath; Remote = "experiments/ffplay/fonts/PocketCinema.ttf" }
  )
  foreach ($runtimeFile in $runtimeFiles) {
    Invoke-Checked "scp" @($scpOptions + @($runtimeFile.Local, "${deviceTarget}:$Destination/$($runtimeFile.Remote)"))
  }
  foreach ($library in $libraries) {
    $source = Join-Path $playerSysroot "usr\lib\$($library.Name)"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
      $source = Join-Path $playerSysroot "lib\$($library.Name)"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
      throw "Missing app-local FFplay runtime library: $($library.Name)"
    }
    Invoke-Checked "scp" @($scpOptions + @($source, "${deviceTarget}:$Destination/experiments/ffplay/lib/$($library.Remote)"))
  }
}

$modeTargets = @(
  "$Destination/launch.sh",
  "$Destination/playback-poc.sh",
  "$Destination/client/pocketcinema-ui.sh",
  "$Destination/client/pocketcinema-proxy.sh",
  "$Destination/client/pocketcinema-connection.sh",
  "$Destination/client/pocketcinema-resource-monitor.sh",
  "$Destination/bin/pocketcinema-selector",
  "$Destination/bin/pocketcinema-pause-monitor",
  "$Destination/bin/pocketcinema-playback-control",
  "$Destination/bin/pocketcinema-discovery",
  "$Destination/bin/pocketcinema-button-diagnostic",
  "$Destination/experiments/button-diagnostic.sh",
  "$Destination/experiments/ffplay/bin/ffplay"
) -join " "
$shellTargets = @(
  "$Destination/launch.sh",
  "$Destination/playback-poc.sh",
  "$Destination/client/pocketcinema-ui.sh",
  "$Destination/client/pocketcinema-proxy.sh",
  "$Destination/client/pocketcinema-connection.sh",
  "$Destination/client/pocketcinema-resource-monitor.sh",
  "$Destination/experiments/button-diagnostic.sh"
) -join " "
$normalize = "for f in $shellTargets; do tr -d '\r' < `"`$f`" > `"`$f.lf`" && mv `"`$f.lf`" `"`$f`" || exit 1; done"
$playerVerifyTargets = @(
  "$Destination/experiments/ffplay/bin/ffplay",
  "$Destination/experiments/ffplay/fonts.conf",
  "$Destination/experiments/ffplay/fonts/PocketCinema.ttf"
) + ($libraries | ForEach-Object { "$Destination/experiments/ffplay/lib/$($_.Remote)" })
$playerVerify = "for f in $($playerVerifyTargets -join ' '); do test -s `"`$f`" || exit 1; done"
$verify = "test -s $Destination/icon.png && $normalize && chmod +x $modeTargets && $playerVerify && /bin/sh -n $Destination/launch.sh && /bin/sh -n $Destination/client/pocketcinema-ui.sh && /bin/sh -n $Destination/client/pocketcinema-proxy.sh && /bin/sh -n $Destination/client/pocketcinema-connection.sh && /bin/sh -n $Destination/client/pocketcinema-resource-monitor.sh"
Invoke-Checked "ssh" ($sshOptions + @($deviceTarget, $verify))
if ($EnableButtonDiagnostic) {
  Invoke-Checked "ssh" ($sshOptions + @($deviceTarget, "touch $Destination/config/button-diagnostic.mode"))
  Write-Output "Button diagnostic mode enabled for the next PocketCinema Apps launch"
}
if ($ReuseInstalledPlayerAssets) {
  Write-Output "PocketCinema deployed using verified existing app-local FFplay subtitle assets; live config and networking-provider state were preserved"
} else {
  Write-Output "PocketCinema deployed with app-local FFplay subtitle assets; live config and networking-provider state were preserved"
}
