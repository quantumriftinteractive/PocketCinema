import urllib.parse


MAX_PLAYLIST_BYTES = 1024 * 1024
MAX_PLAYLIST_LINES = 4096
MAX_URI_LENGTH = 4096
MAX_VIDEO_WIDTH = 640
MAX_VIDEO_HEIGHT = 360
MAX_FRAME_RATE = 30.0
MAX_BANDWIDTH = 1_600_000
MAX_CONVERSION_VIDEO_WIDTH = 1920
MAX_CONVERSION_VIDEO_HEIGHT = 1080
MAX_CONVERSION_BANDWIDTH = 8_000_000

class HlsRelayError(RuntimeError):
    pass


def _attributes(value):
    attributes = {}
    start = 0
    quoted = False
    parts = []
    for index, char in enumerate(value):
        if char == '"':
            quoted = not quoted
        elif char == "," and not quoted:
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    for part in parts:
        key, separator, raw = part.partition("=")
        if separator:
            attributes[key.strip().upper()] = raw.strip().strip('"')
    return attributes


def _positive_number(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _resolution(value):
    try:
        width, height = str(value).lower().split("x", 1)
        return int(width), int(height)
    except (TypeError, ValueError):
        return 0, 0


def _supported_variant(stream_inf, allow_conversion_source=False):
    attributes = _attributes(stream_inf.partition(":")[2])
    width, height = _resolution(attributes.get("RESOLUTION"))
    frame_rate = _positive_number(attributes.get("FRAME-RATE"))
    bandwidth = _positive_number(
        attributes.get("AVERAGE-BANDWIDTH") or attributes.get("BANDWIDTH")
    )
    codecs = attributes.get("CODECS", "").lower()
    has_h264 = "avc1" in codecs or "avc3" in codecs
    return (
        has_h264
        and 0 < width <= (
            MAX_CONVERSION_VIDEO_WIDTH
            if allow_conversion_source
            else MAX_VIDEO_WIDTH
        )
        and 0 < height <= (
            MAX_CONVERSION_VIDEO_HEIGHT
            if allow_conversion_source
            else MAX_VIDEO_HEIGHT
        )
        and (not frame_rate or frame_rate <= MAX_FRAME_RATE)
        and (
            not bandwidth
            or bandwidth
            <= (
                MAX_CONVERSION_BANDWIDTH
                if allow_conversion_source
                else MAX_BANDWIDTH
            )
        )
    )


def _variant_score(stream_inf):
    attributes = _attributes(stream_inf.partition(":")[2])
    width, height = _resolution(attributes.get("RESOLUTION"))
    bandwidth = _positive_number(
        attributes.get("AVERAGE-BANDWIDTH") or attributes.get("BANDWIDTH")
    )
    return width * height, bandwidth


def _resolved_uri(base_url, value, validate_url):
    if not value or len(value) > MAX_URI_LENGTH:
        raise HlsRelayError("The HLS playlist contains an invalid media URI")
    resolved = urllib.parse.urljoin(base_url, value)
    if not validate_url(resolved):
        raise HlsRelayError("The HLS playlist contains a blocked media URI")
    return resolved


def select_variant_url(
    payload, base_url, validate_url, allow_conversion_source=False
):
    if len(payload) > MAX_PLAYLIST_BYTES:
        raise HlsRelayError("The HLS playlist is too large")
    try:
        lines = payload.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise HlsRelayError("The HLS playlist is not valid UTF-8") from exc
    if len(lines) > MAX_PLAYLIST_LINES:
        raise HlsRelayError("The HLS playlist has too many entries")

    variants = []
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        for uri_line in lines[index + 1 :]:
            uri = uri_line.strip()
            if not uri or uri.startswith("#"):
                continue
            if _supported_variant(line, allow_conversion_source):
                variants.append((_variant_score(line), uri))
            break
    if not any(
        raw_line.strip().startswith("#EXT-X-STREAM-INF:") for raw_line in lines
    ):
        return ""
    if not variants:
        raise HlsRelayError("No Miyoo-compatible HLS rendition is available")
    selected_uri = max(variants, key=lambda item: item[0])[1]
    return _resolved_uri(base_url, selected_uri, validate_url)


def parse_media_playlist(payload, base_url, validate_url):
    if len(payload) > MAX_PLAYLIST_BYTES:
        raise HlsRelayError("The HLS playlist is too large")
    try:
        lines = payload.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise HlsRelayError("The HLS playlist is not valid UTF-8") from exc
    if len(lines) > MAX_PLAYLIST_LINES:
        raise HlsRelayError("The HLS playlist has too many entries")
    if not lines or lines[0].strip() != "#EXTM3U":
        raise HlsRelayError("The upstream response is not an HLS playlist")
    if any(line.strip().startswith("#EXT-X-STREAM-INF:") for line in lines):
        raise HlsRelayError("The HLS rendition is not a media playlist")
    if any(line.strip().startswith("#EXT-X-MAP:") for line in lines):
        raise HlsRelayError("Fragmented MP4 HLS is unsupported")
    if any(line.strip().startswith("#EXT-X-BYTERANGE:") for line in lines):
        raise HlsRelayError("Byte-range HLS segments are unsupported")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXT-X-KEY:"):
            method = _attributes(stripped.partition(":")[2]).get("METHOD", "")
            if method and method.upper() != "NONE":
                raise HlsRelayError("Encrypted HLS is unsupported")

    sequence = 0
    target_duration = 6.0
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try:
                sequence = max(0, int(line.partition(":")[2]))
            except ValueError as exc:
                raise HlsRelayError("The HLS media sequence is invalid") from exc
        elif line.startswith("#EXT-X-TARGETDURATION:"):
            target_duration = min(
                30.0, max(1.0, _positive_number(line.partition(":")[2]))
            )

    segments = []
    segment_index = 0
    awaiting_uri = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("#EXTINF:"):
            awaiting_uri = True
            continue
        if awaiting_uri and line and not line.startswith("#"):
            segments.append(
                {
                    "sequence": sequence + segment_index,
                    "url": _resolved_uri(base_url, line, validate_url),
                }
            )
            segment_index += 1
            awaiting_uri = False
    return {
        "segments": segments,
        "target_duration": target_duration,
        "endlist": any(line.strip() == "#EXT-X-ENDLIST" for line in lines),
    }
