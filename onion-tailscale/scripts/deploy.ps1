param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$destination = "/mnt/SDCARD/App/Tailscale"
$sshOptions = @(
  "-o", "MACs=+hmac-sha1",
  "-o", "StrictHostKeyChecking=accept-new"
)

function Invoke-Checked {
  param([string]$Command, [string[]]$Arguments)
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

$tailscale = Join-Path $root "bin\tailscale"
$tailscaled = Join-Path $root "bin\tailscaled"
if (-not (Test-Path -LiteralPath $tailscale -PathType Leaf) -or
    -not (Test-Path -LiteralPath $tailscaled -PathType Leaf)) {
  throw "Install the ignored ARM binaries with scripts/install-from-pc.ps1 first"
}

Invoke-Checked "ssh" ($sshOptions + @(
  $DeviceHost,
  "mkdir -p $destination/bin $destination/scripts $destination/state $destination/logs"
))

$files = @(
  @{ Local = (Join-Path $root "config.json"); Remote = "config.json" },
  @{ Local = (Join-Path $root "launch.sh"); Remote = "launch.sh" },
  @{ Local = $tailscale; Remote = "bin/tailscale" },
  @{ Local = $tailscaled; Remote = "bin/tailscaled" }
)
Get-ChildItem -LiteralPath (Join-Path $root "scripts") -Filter "*.sh" | ForEach-Object {
  $files += @{ Local = $_.FullName; Remote = "scripts/$($_.Name)" }
}
foreach ($file in $files) {
  Invoke-Checked "scp" ($sshOptions + @(
    $file.Local,
    "${DeviceHost}:$destination/$($file.Remote)"
  ))
}

$verify = "chmod +x $destination/launch.sh $destination/bin/tailscale " +
  "$destination/bin/tailscaled $destination/scripts/*.sh && " +
  "/bin/sh -n $destination/launch.sh $destination/scripts/*.sh"
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, $verify))
Write-Output "Tailscale app deployed without copying or modifying node state"
