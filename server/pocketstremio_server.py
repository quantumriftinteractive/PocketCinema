#!/usr/bin/env python3
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


MEDIA = [
    {
        "id": "mock-alien-1979",
        "title": "Alien",
        "type": "movie",
        "year": 1979,
        "runtime_minutes": 117,
    },
    {
        "id": "mock-aliens-1986",
        "title": "Aliens",
        "type": "movie",
        "year": 1986,
        "runtime_minutes": 137,
    },
    {
        "id": "mock-arrival-2016",
        "title": "Arrival",
        "type": "movie",
        "year": 2016,
        "runtime_minutes": 116,
    },
]


class PocketStremioHandler(BaseHTTPRequestHandler):
    server_version = "PocketStremioPOC/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.write_json(
                {
                    "status": "ok",
                    "service": "pocketstremio-server",
                    "version": "0.1-poc",
                    "message": "PocketStremio JSON POC is reachable",
                }
            )
            return

        if parsed.path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            results = [
                item for item in MEDIA if not query or query in item["title"].lower()
            ]
            self.write_json({"query": query, "count": len(results), "results": results})
            return

        if parsed.path == "/media/test-video.mp4":
            self.write_file(self.server.media_dir / "test-video.mp4")
            return

        self.write_json({"error": "not_found", "path": parsed.path}, status=404)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_file(self, path):
        if not path.is_file():
            self.write_json(
                {
                    "error": "missing_media",
                    "message": "Place a compatible MP4 at server/media/test-video.mp4",
                },
                status=404,
            )
            return

        file_size = path.stat().st_size
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        range_header = self.headers.get("Range", "")
        if range_header.startswith("bytes="):
            start_text, _, end_text = range_header[6:].partition("-")
            try:
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else file_size - 1
                end = min(end, file_size - 1)
                if start < 0 or start > end:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            self.stream_file_range(path, start, end)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        self.stream_file_range(path, 0, file_size - 1)

    def stream_file_range(self, path, start, end):
        remaining = end - start + 1
        with path.open("rb") as f:
            f.seek(start)
            while remaining > 0:
                chunk = f.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser(description="Minimal PocketStremio POC server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8755)
    parser.add_argument(
        "--media-dir",
        default=str(Path(__file__).resolve().parent / "media"),
        help="Directory containing test-video.mp4 for playback experiments",
    )
    args = parser.parse_args()

    media_dir = Path(args.media_dir).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), PocketStremioHandler)
    httpd.media_dir = media_dir
    print(f"PocketStremio POC server listening on http://{args.host}:{args.port}", flush=True)
    print(f"Media directory: {media_dir}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
