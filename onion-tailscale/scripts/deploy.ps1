param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost,
  [switch]$ReuseInstalledBinaries
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
$selector = Join-Path $root "bin\onion-tailscale-selector"
if (-not (Test-Path -LiteralPath $selector -PathType Leaf)) {
  throw "Build the committed selector before deployment"
}
if (-not $ReuseInstalledBinaries -and
    (-not (Test-Path -LiteralPath $tailscale -PathType Leaf) -or
     -not (Test-Path -LiteralPath $tailscaled -PathType Leaf))) {
  throw "Install Tailscale binaries or pass -ReuseInstalledBinaries to retain verified device binaries"
}

Invoke-Checked "ssh" ($sshOptions + @(
  $DeviceHost,
  "mkdir -p $destination/bin $destination/boot $destination/scripts " +
  "$destination/state $destination/logs"
))

$files = @(
  @{ Local = (Join-Path $root "config.json"); Remote = "config.json" },
  @{ Local = (Join-Path $root "launch.sh"); Remote = "launch.sh" },
  @{ Local = $selector; Remote = "bin/onion-tailscale-selector" }
)
if (-not $ReuseInstalledBinaries) {
  $files += @(
    @{ Local = $tailscale; Remote = "bin/tailscale" },
    @{ Local = $tailscaled; Remote = "bin/tailscaled" }
  )
}
Get-ChildItem -LiteralPath (Join-Path $root "boot") -Filter "*.sh" | ForEach-Object {
  $files += @{ Local = $_.FullName; Remote = "boot/$($_.Name)" }
}
Get-ChildItem -LiteralPath (Join-Path $root "scripts") -Filter "*.sh" | ForEach-Object {
  $files += @{ Local = $_.FullName; Remote = "scripts/$($_.Name)" }
}
foreach ($file in $files) {
  Invoke-Checked "scp" ($sshOptions + @(
    $file.Local,
    "${DeviceHost}:$destination/$($file.Remote)"
  ))
}

$verify = "test -x $destination/bin/tailscale && test -x $destination/bin/tailscaled && " +
  "chmod +x $destination/launch.sh $destination/bin/onion-tailscale-selector " +
  "$destination/boot/*.sh " +
  "$destination/scripts/*.sh && /bin/sh -n $destination/launch.sh " +
  "$destination/boot/*.sh $destination/scripts/*.sh"
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, $verify))
if ($ReuseInstalledBinaries) {
  Write-Output "Tailscale app deployed with existing device binaries; node state and logs were preserved"
} else {
  Write-Output "Tailscale app deployed without copying or modifying node state"
}
