param(
  [Parameter(Mandatory = $true)]
  [string]$DeviceHost
)

$ErrorActionPreference = "Stop"
$Destination = "/mnt/SDCARD/App/PocketStremio"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
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

$directories = @(
  $Destination,
  "$Destination/client",
  "$Destination/bin",
  "$Destination/config",
  "$Destination/logs"
) -join " "
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, "mkdir -p $directories"))

$files = @(
  @{ Local = "app/config.json"; Remote = "config.json" },
  @{ Local = "app/launch.sh"; Remote = "launch.sh" },
  @{ Local = "app/playback-poc.sh"; Remote = "playback-poc.sh" },
  @{ Local = "client/miyoo/pocketstremio-ui.sh"; Remote = "client/pocketstremio-ui.sh" },
  @{ Local = "client/miyoo/bin/pocketstremio-selector"; Remote = "bin/pocketstremio-selector" },
  @{ Local = "client/miyoo/bin/pocketstremio-pause-monitor"; Remote = "bin/pocketstremio-pause-monitor" },
  @{ Local = "client/miyoo/pocketstremio.conf.example"; Remote = "config/pocketstremio.conf.example" }
)
foreach ($file in $files) {
  $localPath = Join-Path $root $file.Local
  Invoke-Checked "scp" ($sshOptions + @($localPath, "${DeviceHost}:$Destination/$($file.Remote)"))
}

$modeTargets = @(
  "$Destination/launch.sh",
  "$Destination/playback-poc.sh",
  "$Destination/client/pocketstremio-ui.sh",
  "$Destination/bin/pocketstremio-selector",
  "$Destination/bin/pocketstremio-pause-monitor"
) -join " "
$verify = "chmod +x $modeTargets && /bin/sh -n $Destination/launch.sh && /bin/sh -n $Destination/client/pocketstremio-ui.sh"
Invoke-Checked "ssh" ($sshOptions + @($DeviceHost, $verify))
Write-Output "PocketStremio deployed without modifying config/pocketstremio.conf or Tailscale state"
