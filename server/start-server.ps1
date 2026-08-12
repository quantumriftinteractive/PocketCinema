param(
  [string]$HostAddress = "100.85.171.67",
  [int]$Port = 8755,
  [string]$PublicHost = $HostAddress,
  [string]$StremioServiceUrl = "http://127.0.0.1:11470"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
python (Join-Path $PSScriptRoot "pocketstremio_server.py") --host $HostAddress --port $Port --public-host $PublicHost --stremio-service-url $StremioServiceUrl
