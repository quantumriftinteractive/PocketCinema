param(
  [Parameter(Mandatory = $true)]
  [string]$RuntimeRoot,
  [string]$OutputRoot = "dist/PocketCinema-Miyoo-v1.0.0"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$output = [IO.Path]::GetFullPath((Join-Path $root $OutputRoot))

if (Test-Path -LiteralPath $output) {
  throw "Output already exists; remove it explicitly before rebuilding: $output"
}

$files = @(
  @{ Source = "app/config.json"; Destination = "config.json" },
  @{ Source = "app/icon.png"; Destination = "icon.png" },
  @{ Source = "app/launch.sh"; Destination = "launch.sh" },
  @{ Source = "client/miyoo/pocketcinema-ui.sh"; Destination = "client/pocketcinema-ui.sh" },
  @{ Source = "client/miyoo/pocketcinema-proxy.sh"; Destination = "client/pocketcinema-proxy.sh" },
  @{ Source = "client/miyoo/pocketcinema-connection.sh"; Destination = "client/pocketcinema-connection.sh" },
  @{ Source = "client/miyoo/pocketcinema-resource-monitor.sh"; Destination = "client/pocketcinema-resource-monitor.sh" },
  @{ Source = "client/miyoo/bin/pocketcinema-selector"; Destination = "bin/pocketcinema-selector" },
  @{ Source = "client/miyoo/bin/pocketcinema-pause-monitor"; Destination = "bin/pocketcinema-pause-monitor" },
  @{ Source = "client/miyoo/bin/pocketcinema-playback-control"; Destination = "bin/pocketcinema-playback-control" },
  @{ Source = "client/miyoo/bin/pocketcinema-discovery"; Destination = "bin/pocketcinema-discovery" },
  @{ Source = "client/miyoo/pocketcinema.conf.example"; Destination = "config/pocketcinema.conf.example" },
  @{ Source = "experiments/ffplay/fonts.conf"; Destination = "experiments/ffplay/fonts.conf" }
)

$runtimeFiles = @(
  "experiments/ffplay/bin/ffplay",
  "experiments/ffplay/fonts/PocketCinema.ttf",
  "experiments/ffplay/lib/libSDL-1.2.so.0",
  "experiments/ffplay/lib/libass.so.9",
  "experiments/ffplay/lib/libbz2.so.1.0",
  "experiments/ffplay/lib/libz.so.1",
  "experiments/ffplay/lib/libfontconfig.so.1",
  "experiments/ffplay/lib/libfreetype.so.6",
  "experiments/ffplay/lib/libfribidi.so.0",
  "experiments/ffplay/lib/libharfbuzz.so.0",
  "experiments/ffplay/lib/libglib-2.0.so.0",
  "experiments/ffplay/lib/libpcre.so.1",
  "experiments/ffplay/lib/libexpat.so.1",
  "experiments/ffplay/lib/libpng16.so.16",
  "experiments/ffplay/lib/libffi.so.8",
  "experiments/ffplay/lib/libuuid.so.1",
  "experiments/ffplay/lib/libts.so.0"
)

foreach ($entry in $files) {
  $source = Join-Path $root $entry.Source
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Missing package source: $source"
  }
}
foreach ($relative in $runtimeFiles) {
  $source = Join-Path $runtime $relative
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Missing prebuilt runtime asset: $source"
  }
}

New-Item -ItemType Directory -Force -Path @(
  $output,
  (Join-Path $output "client"),
  (Join-Path $output "bin"),
  (Join-Path $output "config"),
  (Join-Path $output "logs"),
  (Join-Path $output "experiments/ffplay/bin"),
  (Join-Path $output "experiments/ffplay/fonts"),
  (Join-Path $output "experiments/ffplay/lib")
) | Out-Null

foreach ($entry in $files) {
  $destination = Join-Path $output $entry.Destination
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
  Copy-Item -LiteralPath (Join-Path $root $entry.Source) -Destination $destination
}
foreach ($relative in $runtimeFiles) {
  $destination = Join-Path $output $relative
  Copy-Item -LiteralPath (Join-Path $runtime $relative) -Destination $destination
}

& chmod +x @(
  (Join-Path $output "launch.sh"),
  (Join-Path $output "client/pocketcinema-ui.sh"),
  (Join-Path $output "client/pocketcinema-proxy.sh"),
  (Join-Path $output "client/pocketcinema-connection.sh"),
  (Join-Path $output "client/pocketcinema-resource-monitor.sh"),
  (Join-Path $output "bin/pocketcinema-selector"),
  (Join-Path $output "bin/pocketcinema-pause-monitor"),
  (Join-Path $output "bin/pocketcinema-playback-control"),
  (Join-Path $output "bin/pocketcinema-discovery"),
  (Join-Path $output "experiments/ffplay/bin/ffplay")
)

Write-Output "Created clean PocketCinema Miyoo package: $output"
