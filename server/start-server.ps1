param(
  [string]$HostAddress = "100.85.171.67",
  [int]$Port = 8755
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
python (Join-Path $PSScriptRoot "pocketstremio_server.py") --host $HostAddress --port $Port
