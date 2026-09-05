import shutil
import re
import secrets
import subprocess
import sys
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


def supports_subtitle_burn_in(ffmpeg_path):
    if not ffmpeg_path:
        return False
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(
        re.search(rb"(?:^|\n).{0,8}\bsubtitles\b", result.stdout)
    )


def needs_downscale(compatibility):
    width = int(compatibility.get("width") or 0)
    height = int(compatibility.get("height") or 0)
    frame_rate = float(compatibility.get("frame_rate") or 0)
    profile = str(compatibility.get("video_profile") or "").lower()
    video_codec = str(compatibility.get("video_codec") or "").lower()
    audio_codec = str(compatibility.get("audio_codec") or "").lower()
    # These codecs are acceptable bounded PCServer inputs but not direct Miyoo
    # profiles.  HLS remains on its independently confirmed MPEG-TS bridge.
    codec_conversion = video_codec in {"hevc", "vp9", "mpeg4"} or audio_codec == "eac3"
    return (
        width > MAX_WIDTH
        or height > MAX_HEIGHT
        or frame_rate > MAX_FRAME_RATE
        or "10" in profile
        or codec_conversion
    )


def conversion_geometry_supported(compatibility):
    """Whether the unchanged 640x360 aspect-preserving filter yields 4:2:0 size."""
    width = int(compatibility.get("width") or 0)
    height = int(compatibility.get("height") or 0)
    if width <= 0 or height <= 0:
        return True
    scale = min(MAX_WIDTH / width, MAX_HEIGHT / height)
    output_width = int(round(width * scale))
    output_height = int(round(height * scale))
    return output_width > 0 and output_height > 0 and output_width % 2 == 0 and output_height % 2 == 0


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
    stripped = payload.lstrip()
    if stripped.startswith(b"WEBVTT"):
        return ".vtt"
    if re.search(rb"(?:^|\n)\[Script Info\]", stripped, re.IGNORECASE):
        return ".ass"
    if stripped.startswith(b"<?xml") or re.search(rb"<tt(?:\s|>)", stripped):
        return ".ttml"
    return ".srt"


def normalize_subtitle_payload(ffmpeg_path, payload, directory):
    """Store SRT/WebVTT directly or convert other text subtitle formats to SRT.

    The conversion input and output stay in PCServer's app-local transcode directory;
    neither an upstream subtitle URL nor arbitrary source path reaches FFmpeg.
    Image-based subtitles are deliberately not OCR'd and fail as unsupported.
    """
    directory = Path(directory)
    suffix = subtitle_suffix(payload)
    token = secrets.token_hex(8)
    source_path = directory / f"subtitle-source-{token}{suffix}"
    source_path.write_bytes(payload)
    if suffix in {".srt", ".vtt"}:
        return source_path

    normalized_path = directory / f"subtitle-{token}.srt"
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        source_path.name,
        "-map",
        "0:s:0",
        "-c:s",
        "srt",
        "-f",
        "srt",
        normalized_path.name,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not normalized_path.is_file() or not normalized_path.stat().st_size:
            raise OSError("Subtitle format is unsupported")
        return normalized_path
    finally:
        source_path.unlink(missing_ok=True)
        if not normalized_path.is_file() or not normalized_path.stat().st_size:
            normalized_path.unlink(missing_ok=True)


def build_command(
    ffmpeg_path,
    input_url,
    subtitle_filename="",
    start_seconds=0,
    audio_stream_index=0,
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
            f"0:a:{max(0, int(audio_stream_index))}?",
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
    audio_stream_index=0,
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
        "fps=30",
    ]
    command.extend(
        ["-map", "0:v:0", "-map", f"0:a:{max(0, int(audio_stream_index))}?"]
    )
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
    """Package one subtitle track in Matroska for the legacy field test."""
    return build_subtitles_matroska_command(
        ffmpeg_path, [(subtitle_filename, input_format, "English")]
    )


def build_subtitles_matroska_command(ffmpeg_path, subtitle_inputs):
    """Package a bounded set of server-local text tracks into Matroska."""
    subtitle_inputs = tuple(subtitle_inputs)
    if not subtitle_inputs:
        raise ValueError("At least one subtitle track is required")
    if len(subtitle_inputs) > 15:
        raise ValueError("Too many subtitle tracks")
    command = [ffmpeg_path, "-hide_banner", "-loglevel", "warning", "-nostdin"]
    normalized_inputs = []
    for item in subtitle_inputs:
        if len(item) == 3:
            filename, input_format, title = item
            language = "eng"
        else:
            filename, input_format, title, language = item
        normalized_inputs.append((filename, input_format, title, language))
        command.extend(["-f", input_format, "-i", filename])
    for index, (_filename, _input_format, title, language) in enumerate(normalized_inputs):
        command.extend(
            [
                "-map",
                f"{index}:0",
                "-metadata:s:s:%d" % index,
                "language=" + str(language or "und")[:12],
                "-metadata:s:s:%d" % index,
                "title=" + str(title)[:80],
            ]
        )
    command.extend(["-c:s", "srt", "-f", "matroska", "pipe:1"])
    return command
