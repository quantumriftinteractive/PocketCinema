import shutil
from pathlib import Path


MAX_WIDTH = 640
MAX_HEIGHT = 360
MAX_FRAME_RATE = 30.0


def resolve_ffmpeg(configured=""):
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() else ""
    return shutil.which("ffmpeg") or ""


def needs_downscale(compatibility):
    width = int(compatibility.get("width") or 0)
    height = int(compatibility.get("height") or 0)
    frame_rate = float(compatibility.get("frame_rate") or 0)
    profile = str(compatibility.get("video_profile") or "").lower()
    return (
        width > MAX_WIDTH
        or height > MAX_HEIGHT
        or frame_rate > MAX_FRAME_RATE
        or "10" in profile
    )


def playback_mode(compatibility):
    status = str(compatibility.get("status") or "candidate")
    if status == "unsupported":
        return "blocked"
    if needs_downscale(compatibility):
        return "convert"
    if status == "confirmed":
        return "direct"
    return "check"


def subtitle_suffix(payload):
    return ".vtt" if payload.lstrip().startswith(b"WEBVTT") else ".srt"


def build_command(
    ffmpeg_path,
    input_url,
    subtitle_filename="",
    start_seconds=0,
):
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
    ]
    if start_seconds > 0:
        command.extend(["-ss", str(int(start_seconds))])
    command.extend(["-re", "-i", input_url])

    filters = [
        "scale=640:360:force_original_aspect_ratio=decrease",
        "pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "fps=30",
    ]
    if subtitle_filename:
        if start_seconds > 0:
            filters.append(f"setpts=PTS+{int(start_seconds)}/TB")
        filters.append(f"subtitles={subtitle_filename}")
        if start_seconds > 0:
            filters.append("setpts=PTS-STARTPTS")
    command.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "main",
            "-level:v",
            "3.0",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "700k",
            "-maxrate",
            "900k",
            "-bufsize",
            "1400k",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-f",
            "mpegts",
            "pipe:1",
        ]
    )
    return command
