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
$source = Join-Path $root "client\miyoo\sdl_selector.c"
$qrSource = Join-Path $root "client\miyoo\third_party\qrcodegen\qrcodegen.c"
$qrInclude = Join-Path $root "client\miyoo\third_party\qrcodegen"
$committed = Join-Path $root "client\miyoo\bin\pocketstremio-selector"
$outputDir = Join-Path $root ".tmp\build-miyoo"
$output = Join-Path $outputDir "pocketstremio-selector"

if (-not (Test-Path -LiteralPath $gcc -PathType Leaf)) {
  throw "ARM compiler not found: $gcc"
}
if (-not (Test-Path -LiteralPath (Join-Path $sysrootPath "usr\include\SDL\SDL.h") -PathType Leaf)) {
  throw "Miyoo SDL sysroot not found: $sysrootPath"
}
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$unixSysroot = $sysrootPath -replace '\\', '/'
$arguments = @(
  "--sysroot=$unixSysroot",
  "-Wall", "-Wextra", "-Werror", "-O2",
  "-I$unixSysroot/usr/include/SDL",
  "-I$($qrInclude -replace '\\', '/')",
  $source,
  $qrSource,
  "-L$unixSysroot/usr/lib",
  "-Wl,-rpath-link,$unixSysroot/usr/lib",
  "-lSDL", "-lts",
  "-o", $output
)
& $gcc @arguments
if ($LASTEXITCODE -ne 0) {
  throw "selector build failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
Write-Output "Built $output"
Write-Output "SHA256 $hash"
if ($VerifyCommitted) {
  $committedHash = (Get-FileHash -LiteralPath $committed -Algorithm SHA256).Hash
  if ($hash -ne $committedHash) {
    throw "rebuilt selector does not match committed binary: $hash != $committedHash"
  }
  Write-Output "Committed selector matches reproducible build"
}
