param(
  [string]$Version = "1.102.2",
  [string]$Arch = "arm",
  [string]$Destination = (Join-Path $PSScriptRoot ".."),
  [string]$DownloadDir = (Join-Path $PSScriptRoot "..\downloads")
)

$ErrorActionPreference = "Stop"
$Destination = (Resolve-Path -LiteralPath $Destination).Path
$DownloadDir = [System.IO.Path]::GetFullPath($DownloadDir)
$url = "https://pkgs.tailscale.com/stable/tailscale_${Version}_${Arch}.tgz"
$archive = Join-Path $DownloadDir "tailscale_${Version}_${Arch}.tgz"
$shaUrl = "$url.sha256"
$shaFile = "$archive.sha256"
$extractDir = Join-Path $DownloadDir "extract"
$packageDir = Join-Path $extractDir "tailscale_${Version}_${Arch}"

New-Item -ItemType Directory -Force -Path $DownloadDir, (Join-Path $Destination "bin"), (Join-Path $Destination "state"), (Join-Path $Destination "logs") | Out-Null

Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $archive

Write-Host "Downloading $shaUrl"
Invoke-WebRequest -Uri $shaUrl -OutFile $shaFile
$expected = ((Get-Content -Raw -LiteralPath $shaFile).Trim() -split "\s+")[0].ToLowerInvariant()
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
  throw "SHA256 mismatch. Expected $expected but got $actual"
}

if (Test-Path -LiteralPath $extractDir) {
  Remove-Item -LiteralPath $extractDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
tar -xzf $archive -C $extractDir

Copy-Item -LiteralPath (Join-Path $packageDir "tailscale") -Destination (Join-Path $Destination "bin\tailscale") -Force
Copy-Item -LiteralPath (Join-Path $packageDir "tailscaled") -Destination (Join-Path $Destination "bin\tailscaled") -Force

Write-Host "Installed Tailscale $Version ($Arch) into $(Join-Path $Destination "bin")"
Write-Host "Copy this app directory to /mnt/SDCARD/App/Tailscale on the Miyoo."
