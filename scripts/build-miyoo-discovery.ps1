param(
  [string]$CompilerRoot = ".tmp\arm-gnu",
  [string]$Sysroot = ".tmp\toolchain\mmiyoo\arm-buildroot-linux-gnueabihf\sysroot",
  [switch]$VerifyCommitted
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$compilerRootPath = Join-Path $root $CompilerRoot
$sysrootPath = Join-Path $root $Sysroot
$gcc = Join-Path $compilerRootPath "bin\arm-none-linux-gnueabihf-gcc.exe"
$source = Join-Path $root "client\miyoo\pocketstremio_discovery.c"
$committed = Join-Path $root "client\miyoo\bin\pocketstremio-discovery"
$outputDir = Join-Path $root ".tmp\build-miyoo"
$output = Join-Path $outputDir "pocketstremio-discovery"

if (-not (Test-Path -LiteralPath $gcc -PathType Leaf)) {
  throw "ARM compiler not found: $gcc"
}
if (-not (Test-Path -LiteralPath $sysrootPath -PathType Container)) {
  throw "Miyoo sysroot not found: $sysrootPath"
}
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$unixSysroot = $sysrootPath -replace '\\', '/'
$arguments = @(
  "--sysroot=$unixSysroot",
  "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
  $source,
  "-o", $output
)
& $gcc @arguments
if ($LASTEXITCODE -ne 0) {
  throw "discovery client build failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
Write-Output "Built $output"
Write-Output "SHA256 $hash"
if ($VerifyCommitted) {
  $committedHash = (Get-FileHash -LiteralPath $committed -Algorithm SHA256).Hash
  if ($hash -ne $committedHash) {
    throw "rebuilt discovery client does not match committed binary: $hash != $committedHash"
  }
  Write-Output "Committed discovery client matches reproducible build"
}
