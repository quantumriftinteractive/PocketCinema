import shutil
import re
from pathlib import Path


MAX_WIDTH = 640
MAX_HEIGHT = 360
MAX_FRAME_RATE = 30.0
SUBTITLE_TIMING_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})"
)


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


def build_matroska_command(
    ffmpeg_path,
    input_url,
    subtitle_filenames=(),
    start_seconds=0,
):
    """Build the opt-in embedded-subtitle field-test command.

    This deliberately remains separate from the production MPEG-TS command.
    The caller supplies only server-local subtitle filenames; upstream URLs
    stay inside the server process and FFmpeg receives an opaque loopback URL.
    """
    subtitle_filenames = tuple(subtitle_filenames)
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
    for filename in subtitle_filenames:
        command.extend(["-i", filename])

    filters = [
        "scale=640:360:force_original_aspect_ratio=decrease",
        "pad=640:360:(ow-iw)/2:(oh-ih)/2:black",
        "fps=30",
    ]
    command.extend(["-map", "0:v:0", "-map", "0:a:0?"])
    for index in range(len(tuple(subtitle_filenames))):
        command.extend(["-map", f"{index + 1}:0"])
    command.extend(
        [
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
            "-c:s",
            "srt",
            "-metadata:s:s:0",
            "language=eng",
            "-f",
            "matroska",
            "pipe:1",
        ]
    )
    return command


def shift_subtitle_payload(payload, offset_seconds):
    """Shift SRT/WebVTT cues to the post-resume timeline."""
    if offset_seconds <= 0:
        return payload
    text = payload.decode("utf-8-sig")
    blocks = re.split(r"(?:\r?\n){2,}", text.strip())
    output = []

    def parse_timestamp(value):
        hours, minutes, seconds = value.replace(",", ".").split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def format_timestamp(seconds, separator):
        seconds = max(0.0, seconds)
        whole = int(seconds)
        millis = int(round((seconds - whole) * 1000))
        if millis >= 1000:
            whole += 1
            millis = 0
        hours, remainder = divmod(whole, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"

    for block in blocks:
        match = SUBTITLE_TIMING_RE.search(block)
        if not match:
            output.append(block)
            continue
        start = parse_timestamp(match.group("start"))
        end = parse_timestamp(match.group("end"))
        if end <= offset_seconds:
            continue
        separator = "," if "," in match.group("start") else "."
        replacement = (
            f"{format_timestamp(start - offset_seconds, separator)} --> "
            f"{format_timestamp(end - offset_seconds, separator)}"
        )
        output.append(SUBTITLE_TIMING_RE.sub(replacement, block, count=1))
    return ("\n\n".join(output) + "\n").encode("utf-8")


def build_subtitle_matroska_command(ffmpeg_path, subtitle_filename, input_format="srt"):
    """Package one subtitle track in Matroska for the opt-in FFplay test."""
    return [
        ffmpeg_path, "-hide_banner", "-loglevel", "warning", "-nostdin",
        "-f", input_format, "-i", subtitle_filename,
        "-map", "0:0", "-c:s", "srt", "-metadata:s:s:0", "language=eng",
        "-f", "matroska", "pipe:1",
    ]
