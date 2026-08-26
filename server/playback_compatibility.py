import json
import shutil
import subprocess
from pathlib import Path


SUPPORTED_CONTAINERS = {
    "avi",
    "hls",
    "matroska",
    "mov",
    "mp4",
    "mpegts",
    "ogg",
    "webm",
}
SUPPORTED_VIDEO_CODECS = {"h264", "hevc", "mpeg4", "vp8", "vp9"}
# These are bounded PSS input codecs, not a claim that every one can be sent
# directly to Miyoo FFplay.  Candidate profiles are converted to AAC first.
SUPPORTED_AUDIO_CODECS = {"aac", "ac3", "eac3", "mp3", "vorbis"}
LANGUAGE_ALIASES = {
    "af": "afr",
    "afr": "afr",
    "sq": "sqi",
    "alb": "sqi",
    "sqi": "sqi",
    "ar": "ara",
    "ara": "ara",
    "hy": "hye",
    "arm": "hye",
    "hye": "hye",
    "az": "aze",
    "aze": "aze",
    "eu": "eus",
    "baq": "eus",
    "eus": "eus",
    "be": "bel",
    "bel": "bel",
    "bn": "ben",
    "ben": "ben",
    "bs": "bos",
    "bos": "bos",
    "bg": "bul",
    "bul": "bul",
    "ca": "cat",
    "cat": "cat",
    "zh": "zho",
    "chi": "zho",
    "zho": "zho",
    "hr": "hrv",
    "hrv": "hrv",
    "cs": "ces",
    "cze": "ces",
    "ces": "ces",
    "da": "dan",
    "dan": "dan",
    "nl": "nld",
    "dut": "nld",
    "nld": "nld",
    "en": "eng",
    "eng": "eng",
    "english": "eng",
    "et": "est",
    "est": "est",
    "tl": "fil",
    "fil": "fil",
    "fi": "fin",
    "fin": "fin",
    "fr": "fra",
    "fre": "fra",
    "fra": "fra",
    "ka": "kat",
    "geo": "kat",
    "kat": "kat",
    "de": "deu",
    "ger": "deu",
    "deu": "deu",
    "es": "spa",
    "spa": "spa",
    "spanish": "spa",
    "el": "ell",
    "ell": "ell",
    "gre": "ell",
    "greek": "ell",
    "he": "heb",
    "iw": "heb",
    "heb": "heb",
    "hi": "hin",
    "hin": "hin",
    "hu": "hun",
    "hun": "hun",
    "is": "isl",
    "ice": "isl",
    "isl": "isl",
    "id": "ind",
    "in": "ind",
    "ind": "ind",
    "it": "ita",
    "ita": "ita",
    "ja": "jpn",
    "jpn": "jpn",
    "ko": "kor",
    "kor": "kor",
    "lv": "lav",
    "lav": "lav",
    "lt": "lit",
    "lit": "lit",
    "mk": "mkd",
    "mac": "mkd",
    "mkd": "mkd",
    "ms": "msa",
    "may": "msa",
    "msa": "msa",
    "ml": "mal",
    "mal": "mal",
    "mr": "mar",
    "mar": "mar",
    "no": "nor",
    "nor": "nor",
    "fa": "fas",
    "per": "fas",
    "fas": "fas",
    "pl": "pol",
    "pol": "pol",
    "pt": "por",
    "por": "por",
    "ro": "ron",
    "rum": "ron",
    "ron": "ron",
    "ru": "rus",
    "rus": "rus",
    "sr": "srp",
    "srp": "srp",
    "sk": "slk",
    "slo": "slk",
    "slk": "slk",
    "sl": "slv",
    "slv": "slv",
    "sv": "swe",
    "swe": "swe",
    "sw": "swa",
    "swa": "swa",
    "ta": "tam",
    "tam": "tam",
    "te": "tel",
    "tel": "tel",
    "th": "tha",
    "tha": "tha",
    "tr": "tur",
    "tur": "tur",
    "uk": "ukr",
    "ukr": "ukr",
    "ur": "urd",
    "urd": "urd",
    "vi": "vie",
    "vie": "vie",
    "cy": "cym",
    "wel": "cym",
    "cym": "cym",
}


class ProbeError(RuntimeError):
    pass


def normalize_language_tag(value):
    token = str(value or "").strip().lower().replace("_", "-")
    token = token.split("-", 1)[0]
    if not token:
        return ""
    if token in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[token]
    return token if token.isalpha() and 2 <= len(token) <= 3 else ""


def resolve_ffprobe(configured=""):
    if configured:
        path = Path(configured).expanduser()
        return str(path.resolve()) if path.is_file() else ""
    return shutil.which("ffprobe") or ""


def probe_media(ffprobe_path, url, timeout=20):
    if not ffprobe_path:
        raise ProbeError("Media inspection is unavailable")

    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        (
            "format=format_name,duration,bit_rate:"
            "stream=index,codec_type,codec_name,profile,width,height,"
            "avg_frame_rate,r_frame_rate,sample_rate,channels:"
            "stream_tags=language,title"
        ),
        "-of",
        "json",
        url,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("Media inspection timed out") from exc
    except OSError as exc:
        raise ProbeError("Media inspection could not start") from exc

    if result.returncode != 0:
        raise ProbeError("The stream source could not be inspected")
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProbeError("Media inspection returned invalid data") from exc


def _positive_int(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _frame_rate(value):
    try:
        numerator, denominator = str(value or "0/1").split("/", 1)
        denominator_value = float(denominator)
        return round(float(numerator) / denominator_value, 2) if denominator_value else 0.0
    except (TypeError, ValueError):
        return 0.0


def classify_probe(data):
    streams = data.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    format_data = data.get("format") or {}
    containers = {
        token.strip().lower()
        for token in str(format_data.get("format_name") or "").split(",")
        if token.strip()
    }
    video_codec = str(video.get("codec_name") or "").lower()
    audio_codec = str(audio.get("codec_name") or "").lower()
    audio_languages = []
    audio_tracks = []
    for item in streams:
        if item.get("codec_type") != "audio":
            continue
        tags = item.get("tags") or {}
        language = normalize_language_tag(tags.get("language"))
        title = str(tags.get("title") or "").strip()
        if language and language not in audio_languages:
            audio_languages.append(language)
        audio_tracks.append(
            {
                "ordinal": len(audio_tracks),
                "language": language,
                "title": title,
            }
        )
    width = _positive_int(video.get("width"))
    height = _positive_int(video.get("height"))
    average_frame_rate = _frame_rate(video.get("avg_frame_rate"))
    reported_frame_rate = _frame_rate(video.get("r_frame_rate"))
    frame_rate = (
        average_frame_rate
        if 0 < average_frame_rate <= 120
        else reported_frame_rate
        if 0 < reported_frame_rate <= 120
        else 0.0
    )
    bitrate = _positive_int(format_data.get("bit_rate"))
    duration = _positive_int(format_data.get("duration"))

    details = {
        "container": sorted(containers & SUPPORTED_CONTAINERS)[0] if containers & SUPPORTED_CONTAINERS else "",
        "video_codec": video_codec,
        "video_profile": str(video.get("profile") or ""),
        "audio_codec": audio_codec,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "bitrate": bitrate,
        "duration_seconds": duration,
        "audio_channels": _positive_int(audio.get("channels")),
        "audio_sample_rate": _positive_int(audio.get("sample_rate")),
        "audio_languages": audio_languages,
        "audio_tracks": audio_tracks,
    }

    if not video_codec:
        return {"status": "unsupported", "message": "No video track was detected", **details}
    if not containers & SUPPORTED_CONTAINERS:
        return {"status": "unsupported", "message": "The media container is unsupported", **details}
    if video_codec not in SUPPORTED_VIDEO_CODECS:
        return {
            "status": "unsupported",
            "message": f"Video codec {video_codec or 'unknown'} is unsupported",
            **details,
        }
    if audio_codec and audio_codec not in SUPPORTED_AUDIO_CODECS:
        return {
            "status": "unsupported",
            "message": f"Audio codec {audio_codec} is unsupported",
            **details,
        }

    confirmed_h264 = (
        video_codec == "h264"
        and audio_codec == "aac"
        and bool(containers & {"mov", "mp4"})
        and 0 < width <= 640
        and 0 < height <= 360
        and (not frame_rate or frame_rate <= 30.0)
        and (not bitrate or bitrate <= 1_600_000)
        and _positive_int(audio.get("channels")) <= 2
    )
    if confirmed_h264:
        message = "Confirmed Miyoo profile: H.264/AAC MP4 up to 640x360"
        return {"status": "confirmed", "message": message, **details}

    confirmed_vp8 = (
        video_codec == "vp8"
        and audio_codec == "vorbis"
        and bool(containers & {"matroska", "webm"})
        and 0 < width <= 640
        and 0 < height <= 360
        and (not frame_rate or frame_rate <= 30.0)
        and (not bitrate or bitrate <= 600_000)
        and _positive_int(audio.get("channels")) <= 2
        and _positive_int(audio.get("sample_rate")) <= 44_100
    )
    if confirmed_vp8:
        message = "Confirmed Miyoo profile: VP8/Vorbis WebM up to 640x360"
        return {"status": "confirmed", "message": message, **details}

    message = "Decoder available, but this media profile is not physically confirmed"
    return {"status": "candidate", "message": message, **details}


def declared_compatibility(hints):
    declared = (hints or {}).get("pocketstremio") or {}
    status = str(declared.get("status") or "candidate").lower()
    if status not in {"confirmed", "candidate", "unsupported"}:
        status = "candidate"
    message = str(declared.get("message") or "Server preflight required")[:160]
    return {"status": status, "message": message}
