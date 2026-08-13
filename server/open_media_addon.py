#!/usr/bin/env python3
import argparse
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


NIGHT_OF_THE_LIVING_DEAD_ID = "tt0063350"
NIGHT_OF_THE_LIVING_DEAD_URL = (
    "https://archive.org/download/Night.Of.The.Living.Dead_1080p/"
    "NightOfTheLivingDead_DVD5_512kb.mp4"
)

MANIFEST = {
    "id": "org.pocketstremio.open-media",
    "version": "1.0.0",
    "name": "PocketStremio Open Media",
    "description": "Small legal-media source used to validate Stremio stream resolution.",
    "resources": ["stream"],
    "types": ["movie"],
    "idPrefixes": [NIGHT_OF_THE_LIVING_DEAD_ID],
}


class OpenMediaAddonHandler(BaseHTTPRequestHandler):
    server_version = "PocketStremioOpenMedia/1.0"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/manifest.json":
            self.write_json(MANIFEST)
            return

        parts = [urllib.parse.unquote(part) for part in path.split("/") if part]
        if len(parts) == 3 and parts[:2] == ["stream", "movie"]:
            item_id = parts[2].removesuffix(".json")
            streams = []
            if item_id == NIGHT_OF_THE_LIVING_DEAD_ID:
                streams.append(
                    {
                        "name": "Open Media - Internet Archive",
                        "description": "Public domain | H.264/AAC | 320x240 | 512 Kb/s",
                        "url": NIGHT_OF_THE_LIVING_DEAD_URL,
                        "durationSeconds": 5752,
                        "behaviorHints": {
                            "pocketstremio": {
                                "status": "confirmed",
                                "message": "Confirmed H.264/AAC 320x240 profile",
                            }
                        },
                    }
                )
            self.write_json({"streams": streams})
            return

        self.write_json({"error": "not_found"}, status=404)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("open-media-addon: %s - %s" % (self.address_string(), fmt % args), flush=True)


def create_server(host="127.0.0.1", port=8756):
    return ThreadingHTTPServer((host, port), OpenMediaAddonHandler)


def main():
    parser = argparse.ArgumentParser(description="PocketStremio legal open-media addon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8756)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print(f"Open-media addon listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
