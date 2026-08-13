param(
  [string]$HostAddress = "100.85.171.67",
  [int]$Port = 8755,
  [string]$PublicHost = $HostAddress,
  [string]$StremioServiceUrl = "http://127.0.0.1:11470",
  [int]$OpenMediaAddonPort = 8756,
  [string]$FFprobePath = ""
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if (-not $FFprobePath) {
  $stremioFFprobe = Join-Path $env:LOCALAPPDATA "Programs\LNV\Stremio-4\ffprobe.exe"
  if (Test-Path -LiteralPath $stremioFFprobe) {
    $FFprobePath = $stremioFFprobe
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
if ($FFprobePath) {
  $arguments += @("--ffprobe", $FFprobePath)
}
python @arguments
