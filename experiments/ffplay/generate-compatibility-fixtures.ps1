param(
  [string]$FfmpegPath = "$env:LOCALAPPDATA\Programs\LNV\Stremio-4\ffmpeg.exe",
  [string]$SourcePath = ""
)

$ErrorActionPreference = "Stop"
$mediaDir = Join-Path $PSScriptRoot "..\..\server\media"
if (-not $SourcePath) {
  $SourcePath = Join-Path $mediaDir "test-video.mp4"
}

if (-not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
  throw "ffmpeg not found: $FfmpegPath"
}
if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
  throw "source video not found: $SourcePath"
}

$vp8Path = Join-Path $mediaDir "compat-vp8-vorbis.webm"
$opusPath = Join-Path $mediaDir "compat-h264-opus.mkv"

& $FfmpegPath -y -hide_banner -loglevel warning -i $SourcePath `
  -map 0:v:0 -map 0:a:0 `
  -c:v libvpx -deadline good -cpu-used 4 `
  -b:v 500k -maxrate 700k -bufsize 1000k `
  -c:a libvorbis -b:a 64k -ar 44100 -ac 2 `
  $vp8Path
if ($LASTEXITCODE -ne 0) {
  throw "VP8/Vorbis fixture generation failed with exit code $LASTEXITCODE"
}

& $FfmpegPath -y -hide_banner -loglevel warning -i $SourcePath `
  -map 0:v:0 -map 0:a:0 `
  -c:v copy -c:a libopus -b:a 64k -ar 48000 -ac 2 `
  $opusPath
if ($LASTEXITCODE -ne 0) {
  throw "H.264/Opus fixture generation failed with exit code $LASTEXITCODE"
}

Get-Item -LiteralPath $vp8Path, $opusPath |
  Select-Object FullName, Length, LastWriteTime
