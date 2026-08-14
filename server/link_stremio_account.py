import argparse
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path


LINK_BASE = "https://link.stremio.com/api/v2"


def fetch_json(url, timeout=10):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PocketStremio/0.11"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def create_link():
    payload = fetch_json(LINK_BASE + "/create?type=Create")
    result = payload.get("result") or {}
    code = result.get("code")
    link = result.get("link")
    if not isinstance(code, str) or not isinstance(link, str):
        raise RuntimeError("Stremio link service returned an invalid response")
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme != "https" or parsed.hostname != "link.stremio.com":
        raise RuntimeError("Stremio link service returned an unsafe approval URL")
    return code, link


def read_auth_key(code):
    query = urllib.parse.urlencode({"type": "Read", "code": code})
    try:
        payload = fetch_json(LINK_BASE + "/read?" + query)
    except urllib.error.HTTPError as exc:
        if exc.code in {400, 404, 409}:
            return ""
        raise
    result = payload.get("result") or {}
    auth_key = result.get("authKey")
    return auth_key if isinstance(auth_key, str) else ""


def write_config(path, auth_key, replace=False):
    path = Path(path)
    if path.exists() and not replace:
        raise RuntimeError(f"Account config already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as config_file:
            json.dump({"auth_key": auth_key}, config_file)
            config_file.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main():
    parser = argparse.ArgumentParser(
        description="Link a Stremio account without handling its password"
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config" / "stremio_account.json"),
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    code, link = create_link()
    print("Approve PocketStremio using this temporary Stremio link:", flush=True)
    print(link, flush=True)
    if not args.no_browser:
        webbrowser.open(link)
    deadline = time.monotonic() + max(30, args.timeout)
    while time.monotonic() < deadline:
        auth_key = read_auth_key(code)
        if auth_key:
            write_config(args.config, auth_key, replace=args.replace)
            print(f"Stremio account linked. Key stored in ignored config: {args.config}")
            return
        time.sleep(2)
    raise SystemExit("Timed out waiting for Stremio account approval")


if __name__ == "__main__":
    main()
