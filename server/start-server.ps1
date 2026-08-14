param(
  [string]$HostAddress = "100.85.171.67",
  [int]$Port = 8755,
  [string]$PublicHost = $HostAddress,
  [string]$StremioServiceUrl = "http://127.0.0.1:11470",
  [string]$StremioLocalMediaRoot = "",
  [int]$OpenMediaAddonPort = 8756,
  [string]$FFprobePath = "",
  [string]$FFmpegPath = ""
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if (-not $FFprobePath) {
  $stremioFFprobe = Join-Path $env:LOCALAPPDATA "Programs\LNV\Stremio-4\ffprobe.exe"
  if (Test-Path -LiteralPath $stremioFFprobe) {
    $FFprobePath = $stremioFFprobe
  }
}
if (-not $StremioLocalMediaRoot) {
  $candidate = Join-Path $env:USERPROFILE "Videos\PocketStremio"
  if (Test-Path -LiteralPath $candidate -PathType Container) {
    $StremioLocalMediaRoot = $candidate
  }
}
if (-not $FFmpegPath) {
  $stremioFFmpeg = Join-Path $env:LOCALAPPDATA "Programs\LNV\Stremio-4\ffmpeg.exe"
  if (Test-Path -LiteralPath $stremioFFmpeg) {
    $FFmpegPath = $stremioFFmpeg
  }
}

$arguments = @(
  (Join-Path $PSScriptRoot "pocketstremio_server.py")
  "--host", $HostAddress
  "--port", $Port
  "--public-host", $PublicHost
  "--stremio-service-url", $StremioServiceUrl
  "--open-media-addon-port", $OpenMediaAddonPort
)
if ($StremioLocalMediaRoot) {
  $arguments += @("--stremio-local-media-root", $StremioLocalMediaRoot)
}
if ($FFprobePath) {
  $arguments += @("--ffprobe", $FFprobePath)
}
if ($FFmpegPath) {
  $arguments += @("--ffmpeg", $FFmpegPath)
}
python @arguments
