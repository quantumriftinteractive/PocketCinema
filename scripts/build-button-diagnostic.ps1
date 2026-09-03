param(
  [string]$CompilerRoot = ".tmp\arm-gnu",
  [string]$Sysroot = ".tmp\toolchain\mmiyoo\arm-buildroot-linux-gnueabihf\sysroot"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$compilerRootPath = Join-Path $root $CompilerRoot
$sysrootPath = Join-Path $root $Sysroot
$gcc = Join-Path $compilerRootPath "bin\arm-none-linux-gnueabihf-gcc.exe"
$source = Join-Path $root "experiments\button-diagnostic.c"
$outputDir = Join-Path $root ".tmp\build-miyoo"
$output = Join-Path $outputDir "pocketcinema-button-diagnostic"

if (-not (Test-Path -LiteralPath $gcc -PathType Leaf)) {
  throw "ARM compiler not found: $gcc"
}
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$unixSysroot = $sysrootPath -replace '\\', '/'
& $gcc "--sysroot=$unixSysroot" -Wall -Wextra -Werror -O2 $source `
  "-o" $output
if ($LASTEXITCODE -ne 0) {
  throw "button diagnostic build failed with exit code $LASTEXITCODE"
}
Write-Output "Built $output"
Write-Output "SHA256 $((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash)"
