param(
  [string]$FfmpegPath = "$env:LOCALAPPDATA\Programs\LNV\Stremio-4\ffmpeg.exe",
  [int]$DurationSeconds = 30
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
  throw "ffmpeg not found: $FfmpegPath"
}
if ($DurationSeconds -lt 10) {
  throw "DurationSeconds must be at least 10"
}

$mediaDir = Join-Path $PSScriptRoot "..\..\server\media"
$outputPath = Join-Path $mediaDir "series-av-sync.mp4"
$videoSource = "testsrc2=size=640x360:rate=30:duration=$DurationSeconds"
$audioSource = "aevalsrc=if(lt(mod(t\,1)\,0.18)\,0.35*sin(2*PI*880*t)\,0):s=44100:d=$DurationSeconds"
$videoFilter = "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='lt(mod(t,1),0.18)'"

& $FfmpegPath -y -hide_banner -loglevel warning `
  -f lavfi -i $videoSource `
  -f lavfi -i $audioSource `
  -vf $videoFilter `
  -map 0:v:0 -map 1:a:0 `
  -c:v libx264 -profile:v high -level 3.0 -pix_fmt yuv420p `
  -r 30 -g 30 -b:v 800k -maxrate 1200k -bufsize 1600k `
  -c:a aac -b:a 96k -ar 44100 -ac 2 `
  -movflags +faststart -shortest `
  $outputPath
if ($LASTEXITCODE -ne 0) {
  throw "series A/V sync fixture generation failed with exit code $LASTEXITCODE"
}

Get-Item -LiteralPath $outputPath |
  Select-Object FullName, Length, LastWriteTime
