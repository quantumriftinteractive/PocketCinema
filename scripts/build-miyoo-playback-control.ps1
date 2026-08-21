param(
  [string]$Sysroot = ".tmp\toolchain\mmiyoo\arm-buildroot-linux-gnueabihf\sysroot",
  [switch]$VerifyCommitted
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$source = Join-Path $root "client\miyoo\playback_control.c"
$outputDir = Join-Path $root ".tmp\build-miyoo"
$output = Join-Path $outputDir "pocketstremio-playback-control"
$committed = Join-Path $root "client\miyoo\bin\pocketstremio-playback-control"
$sysrootPath = Resolve-Path -LiteralPath (Join-Path $root $Sysroot)
$unixSysroot = $sysrootPath.Path.Replace('\', '/')
$gcc = Join-Path $root ".tmp\arm-gnu\bin\arm-none-linux-gnueabihf-gcc.exe"
if (-not (Test-Path -LiteralPath $gcc)) { throw "Miyoo ARM compiler not found" }
if (-not (Test-Path -LiteralPath (Join-Path $sysrootPath "usr\include\linux\input.h"))) {
  throw "Miyoo sysroot not found: $sysrootPath"
}
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
& $gcc "--sysroot=$unixSysroot" -Wall -Wextra -Werror -O2 $source -o $output
if ($LASTEXITCODE -ne 0) { throw "playback control build failed with exit code $LASTEXITCODE" }
if ($VerifyCommitted) {
  if (-not (Test-Path -LiteralPath $committed)) { throw "Committed playback control binary missing" }
  $builtHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
  $committedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $committed).Hash
  if ($builtHash -ne $committedHash) { throw "Committed playback control binary differs from reproducible build" }
  Write-Output "Committed playback control binary matches reproducible build"
} else {
  Copy-Item -LiteralPath $output -Destination $committed -Force
  Write-Output "Built client/miyoo/bin/pocketstremio-playback-control"
}
