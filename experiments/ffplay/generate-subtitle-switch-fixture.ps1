param(
  [string]$FfmpegPath = "$env:LOCALAPPDATA\Programs\LNV\Stremio-4\ffmpeg.exe",
  [int]$DurationSeconds = 20
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $FfmpegPath -PathType Leaf)) {
  throw "ffmpeg not found: $FfmpegPath"
}
if ($DurationSeconds -lt 10) {
  throw "DurationSeconds must be at least 10"
}

$mediaDir = Join-Path $PSScriptRoot "..\..\server\media"
$trackOne = Join-Path $mediaDir "subtitle-switch-track-one.srt"
$trackTwo = Join-Path $mediaDir "subtitle-switch-track-two.srt"
$outputPath = Join-Path $mediaDir "subtitle-switch-fixture.mkv"
New-Item -ItemType Directory -Path $mediaDir -Force | Out-Null

@"
1
00:00:02,000 --> 00:00:06,000
TRACK ONE - RED / FIRST

2
00:00:08,000 --> 00:00:12,000
TRACK ONE - RED / SECOND

3
00:00:14,000 --> 00:00:18,000
TRACK ONE - RED / THIRD
"@ | Set-Content -LiteralPath $trackOne -Encoding UTF8
@"
1
00:00:02,000 --> 00:00:06,000
TRACK TWO - BLUE / FIRST

2
00:00:08,000 --> 00:00:12,000
TRACK TWO - BLUE / SECOND

3
00:00:14,000 --> 00:00:18,000
TRACK TWO - BLUE / THIRD
"@ | Set-Content -LiteralPath $trackTwo -Encoding UTF8

$videoSource = "testsrc2=size=640x360:rate=30:duration=$DurationSeconds"
$audioSource = "sine=frequency=440:sample_rate=44100:duration=$DurationSeconds"
& $FfmpegPath -y -hide_banner -loglevel warning `
  -f lavfi -i $videoSource -f lavfi -i $audioSource `
  -i $trackOne -i $trackTwo `
  -map 0:v:0 -map 1:a:0 -map 2:0 -map 3:0 `
  -c:v libx264 -profile:v high -level 3.0 -pix_fmt yuv420p `
  -r 30 -g 30 -b:v 800k -maxrate 1200k -bufsize 1600k `
  -c:a aac -b:a 96k -ar 44100 -ac 2 `
  -c:s srt -metadata:s:s:0 language=eng -metadata:s:s:0 title="Track One Red" `
  -metadata:s:s:1 language=eng -metadata:s:s:1 title="Track Two Blue" `
  -shortest $outputPath
if ($LASTEXITCODE -ne 0) {
  throw "subtitle switch fixture generation failed with exit code $LASTEXITCODE"
}
Get-Item -LiteralPath $outputPath | Select-Object FullName, Length, LastWriteTime
