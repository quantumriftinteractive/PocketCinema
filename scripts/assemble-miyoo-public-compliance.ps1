param(
    [Parameter(Mandatory = $true)]
    [string]$ArchiveRoot,
    [string]$Output = "release-sources/miyoo/public",
    [switch]$IncludeArchives
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script = Join-Path $repoRoot "scripts/assemble-miyoo-public-compliance.py"
$args = @("$script", "--archive-root", (Resolve-Path $ArchiveRoot).Path, "--output", (Join-Path $repoRoot $Output))
if ($IncludeArchives) { $args += "--include-archives" }
python @args
