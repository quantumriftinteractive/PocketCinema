param(
  [ValidateSet("start", "stop", "restart", "status")]
  [string]$Action = "status",
  [string]$HostAddress = $env:POCKETSTREMIO_HOST,
  [int]$Port = 8755,
  [string]$PublicHost = "",
  [string]$ServerName = $env:COMPUTERNAME,
  [string]$NetworkName = "Network",
  [int]$DiscoveryPort = 8754,
  [switch]$DisableDiscovery,
  [string]$StremioServiceUrl = "http://127.0.0.1:11470",
  [string]$StremioLocalMediaRoot = "",
  [int]$OpenMediaAddonPort = 8756,
  [string]$FFprobePath = "",
  [string]$FFmpegPath = "",
  [switch]$EnableFieldTest,
  [switch]$EnableMatroskaSubtitles
)

$ErrorActionPreference = "Stop"
if (-not $HostAddress -and $Action -ne "stop") {
  throw "Set POCKETSTREMIO_HOST or pass -HostAddress"
}
if (-not $PublicHost) {
  $PublicHost = $HostAddress
}
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$dataDir = Join-Path $PSScriptRoot "data"
$pidFile = Join-Path $dataDir "server.pid"
$stdoutLog = Join-Path $dataDir "server.stdout.log"
$stderrLog = Join-Path $dataDir "server.stderr.log"
$serverScript = Join-Path $PSScriptRoot "pocketstremio_server.py"
$healthUrl = "http://${HostAddress}:$Port/api/status"

function Get-ManagedProcess {
  if (-not (Test-Path -LiteralPath $pidFile -PathType Leaf)) {
    return $null
  }
  $savedPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  if ($savedPid -notmatch '^\d+$') {
    Remove-Item -LiteralPath $pidFile -Force
    return $null
  }
  $process = Get-CimInstance Win32_Process -Filter "ProcessId = $savedPid" -ErrorAction SilentlyContinue
  if (-not $process -or $process.CommandLine -notlike "*pocketstremio_server.py*") {
    Remove-Item -LiteralPath $pidFile -Force
    return $null
  }
  return $process
}

function Wait-ForHealth {
  param([int]$Attempts = 30)
  for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    try {
      $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
      if ($health.status -eq "ok") {
        return $health
      }
    } catch {
      Start-Sleep -Milliseconds 250
    }
  }
  throw "PocketStremio did not become healthy at $healthUrl"
}

function Start-ManagedServer {
  if (Get-ManagedProcess) {
    throw "PocketStremio server is already running"
  }
  $unmanagedHealth = $null
  try {
    $unmanagedHealth = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
  } catch {
    $unmanagedHealth = $null
  }
  if ($unmanagedHealth -and $unmanagedHealth.status -eq "ok") {
    throw "A PocketStremio server already answers at $healthUrl but is not owned by this manager"
  }
  New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
  if (-not $FFprobePath) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\LNV\Stremio-4\ffprobe.exe"
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      $script:FFprobePath = $candidate
    }
  }
  if (-not $FFmpegPath) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\LNV\Stremio-4\ffmpeg.exe"
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
      $script:FFmpegPath = $candidate
    }
  }
  if (-not $StremioLocalMediaRoot) {
    $candidate = Join-Path $env:USERPROFILE "Videos\PocketStremio"
    if (Test-Path -LiteralPath $candidate -PathType Container) {
      $script:StremioLocalMediaRoot = $candidate
    }
  }

  $arguments = @(
    "-u",
    $serverScript,
    "--host", $HostAddress,
    "--port", $Port,
    "--public-host", $PublicHost,
    "--server-name", $ServerName,
    "--network-name", $NetworkName,
    "--discovery-port", $DiscoveryPort,
    "--stremio-service-url", $StremioServiceUrl,
    "--open-media-addon-port", $OpenMediaAddonPort
  )
  if ($EnableFieldTest) {
    $arguments += "--enable-field-test"
  }
  if ($EnableMatroskaSubtitles) {
    $arguments += "--enable-matroska-subtitles"
  }
  if ($DisableDiscovery) {
    $arguments += "--disable-discovery"
  }
  if ($StremioLocalMediaRoot) {
    $arguments += @("--stremio-local-media-root", $StremioLocalMediaRoot)
  }
  if ($FFprobePath) {
    $arguments += @("--ffprobe", $FFprobePath)
  }
  if ($FFmpegPath) {
    $arguments += @("--ffmpeg", $FFmpegPath)
  }

  $python = (Get-Command python -ErrorAction Stop).Source
  $process = Start-Process -FilePath $python -ArgumentList $arguments `
    -WorkingDirectory $root -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii
  try {
    $health = Wait-ForHealth
  } catch {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw
  }
  Write-Output "PocketStremio started: PID $($process.Id), version $($health.version)"
}

function Stop-ManagedServer {
  $process = Get-ManagedProcess
  if (-not $process) {
    Write-Output "PocketStremio is not running"
    return
  }
  Stop-Process -Id $process.ProcessId
  try {
    Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction Stop
  } catch {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $process.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
  }
  Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
  Write-Output "PocketStremio stopped: PID $($process.ProcessId)"
}

switch ($Action) {
  "start" { Start-ManagedServer }
  "stop" { Stop-ManagedServer }
  "restart" {
    Stop-ManagedServer
    Start-ManagedServer
  }
  "status" {
    $process = Get-ManagedProcess
    if (-not $process) {
      Write-Output "PocketStremio is not running"
      exit 1
    }
    $health = Wait-ForHealth -Attempts 1
    Write-Output "PocketStremio running: PID $($process.ProcessId), version $($health.version), uptime $($health.uptime_seconds)s"
  }
}
