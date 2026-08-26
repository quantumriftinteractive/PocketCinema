$ErrorActionPreference = 'Continue'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

Push-Location $root
try {
  $branch = (& git branch --show-current).Trim()
  $head = (& git rev-parse HEAD 2>$null).Trim()
  $upstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
  if (-not $upstream) { $upstream = 'origin/' + $branch }
  $remoteParts = $upstream -split '/', 2
  $remoteName = $remoteParts[0]
  $remoteBranch = if ($remoteParts.Count -eq 2) { $remoteParts[1] } else { $branch }
  $remoteLine = (& git ls-remote $remoteName "refs/heads/$remoteBranch" 2>$null | Select-Object -First 1)
  $remoteHead = if ($remoteLine) { ($remoteLine -split '\s+')[0] } else { '' }

  $state = Get-Content -Raw PROJECT_STATE.md
  $baseline = ([regex]::Match($state, 'Production baseline commit:\s*`([^`]+)`')).Groups[1].Value
  $milestone = ([regex]::Match($state, 'Active milestone:\s*(.+)')).Groups[1].Value.Trim()
  $checkpoint = ([regex]::Match($state, 'Checkpoint commit:\s*`([^`]+)`')).Groups[1].Value

  $dirty = (& git status --porcelain)
  $ahead = '?'
  $behind = '?'
  $diverged = 'UNKNOWN'
  $sync = 'REMOTE_UNAVAILABLE'
  $remoteObject = $false

  if ($remoteHead) {
    & git cat-file -e "$remoteHead^{commit}" 2>$null
    $remoteObject = $LASTEXITCODE -eq 0
  }
  if ($remoteObject) {
    $counts = (& git rev-list --left-right --count "$head...$remoteHead" 2>$null).Trim().Split()
    if ($counts.Count -eq 2) {
      $ahead = $counts[0]
      $behind = $counts[1]
      $diverged = if ($ahead -gt 0 -and $behind -gt 0) { 'YES' } else { 'NO' }
      $sync = if ($diverged -eq 'YES') {
        'DIVERGED'
      } elseif ($behind -gt 0) {
        'BEHIND_REMOTE'
      } elseif ($ahead -gt 0) {
        'AHEAD_REMOTE'
      } else {
        'OK'
      }
    }
  }
  if ($dirty -and $sync -eq 'OK') { $sync = 'DIRTY' }

  $checkpointReachable = 'UNVERIFIED'
  if ($checkpoint) {
    & git cat-file -e "$checkpoint^{commit}" 2>$null
    $checkpointExists = $LASTEXITCODE -eq 0
    if (-not $checkpointExists) {
      $checkpointReachable = 'NO'
    } elseif ($remoteHead -and $remoteObject) {
      & git merge-base --is-ancestor $checkpoint $remoteHead 2>$null
      $checkpointReachable = if ($LASTEXITCODE -eq 0) { 'YES' } else { 'NO' }
    }
  }

  $remoteHandoff = if ($checkpointReachable -eq 'NO') {
    'INVALID'
  } elseif ($checkpointReachable -eq 'YES' -and $sync -eq 'OK') {
    'VALID'
  } elseif ($checkpointReachable -eq 'YES') {
    'INCOMPLETE'
  } else {
    'UNVERIFIED'
  }

  Write-Output 'PocketStremio Development State'
  Write-Output "Machine/OS: Windows / $([System.Environment]::OSVersion.VersionString)"
  Write-Output "Branch: $branch"
  Write-Output "Local HEAD: $head"
  Write-Output "Remote HEAD: $(if ($remoteHead) { $remoteHead } else { 'UNAVAILABLE' })"
  Write-Output "Production baseline: $baseline"
  Write-Output "Working tree: $(if ($dirty) { 'DIRTY' } else { 'CLEAN' })"
  Write-Output "Ahead: $ahead"
  Write-Output "Behind: $behind"
  Write-Output "Diverged: $diverged"
  Write-Output "Active milestone: $milestone"
  Write-Output "Latest checkpoint commit: $(if ($checkpoint) { $checkpoint } else { 'UNRECORDED' })"
  Write-Output "Checkpoint reachable from origin/main: $checkpointReachable"
  Write-Output "Remote handoff status: $remoteHandoff"
  Write-Output "`nSYNC STATUS: $sync"

  if ($sync -eq 'BEHIND_REMOTE' -or $sync -eq 'DIVERGED') {
    Write-Output "`nDO NOT BEGIN DEVELOPMENT UNTIL THE CHECKOUT IS SYNCHRONIZED."
  }
  if ($sync -eq 'REMOTE_UNAVAILABLE') { Write-Output "`nREMOTE STATUS UNVERIFIED" }
  if ($checkpointReachable -eq 'NO') {
    Write-Output "`nREMOTE HANDOFF INVALID`n"
    Write-Output 'PROJECT_STATE checkpoint is not present in origin/main.'
    Write-Output 'Do not continue development from another machine.'
  }
} finally {
  Pop-Location
}
