import os
import re
import secrets
import socket
import threading
from pathlib import Path


DISCOVERY_PORT = 8754
# The pre-release protocol marker is not shown to users. Keep it stable so the
# renamed client can discover a deployed server without a protocol migration.
DISCOVERY_REQUEST = b"POCKETSTREMIO_DISCOVER_V1\n"
DISCOVERY_RESPONSE_PREFIX = "POCKETSTREMIO_PSS_V1"
MAX_PACKET_BYTES = 1024


def public_url(host, port):
    value = str(host).strip()
    if value.startswith("[") and value.endswith("]"):
        formatted = value
    elif ":" in value:
        formatted = f"[{value}]"
    else:
        formatted = value
    return f"http://{formatted}:{int(port)}"


def safe_name(value):
    cleaned = " ".join(str(value).split())
    cleaned = "".join(character for character in cleaned if 32 <= ord(character) < 127)
    return cleaned[:48] or "PocketCinema"


def load_or_create_instance_id(path):
    destination = Path(path)
    try:
        value = destination.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        value = ""
    if re.fullmatch(r"[a-f0-9]{16,64}", value):
        return value

    value = secrets.token_hex(8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(value + "\n")
    temporary.replace(destination)
    return value


def response_packet(instance_id, name, network, url, version):
    safe_id = str(instance_id).replace("\t", "").replace("\r", "").replace("\n", "")
    safe_server_name = safe_name(name)
    safe_network = safe_name(network)
    safe_url = str(url).replace("\t", "").replace("\r", "").replace("\n", "")
    safe_version = (
        str(version).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    )
    return (
        f"{DISCOVERY_RESPONSE_PREFIX}\t{safe_id}\t{safe_server_name}\t"
        f"{safe_network}\t{safe_url}\t{safe_version}\n"
    ).encode("utf-8")


class DiscoveryResponder:
    def __init__(
        self,
        instance_id,
        name,
        network,
        url,
        version,
        port=DISCOVERY_PORT,
        bind_host="0.0.0.0",
    ):
        self.instance_id = instance_id
        self.name = safe_name(name)
        self.network = safe_name(network)
        self.url = url
        self.version = version
        self.port = int(port)
        self.bind_host = bind_host
        self.bound_port = None
        self._socket = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        sock.bind((self.bind_host, self.port))
        self.bound_port = sock.getsockname()[1]
        self._socket = sock
        self._thread = threading.Thread(
            target=self._serve, name="pocketcinema-discovery", daemon=True
        )
        self._thread.start()
        return self

    def _serve(self):
        packet = response_packet(
            self.instance_id, self.name, self.network, self.url, self.version
        )
        while not self._stop.is_set():
            try:
                request, address = self._socket.recvfrom(MAX_PACKET_BYTES)
            except socket.timeout:
                continue
            except OSError:
                break
            if request != DISCOVERY_REQUEST:
                continue
            try:
                self._socket.sendto(packet, address)
            except OSError:
                if self._stop.is_set():
                    break

    def close(self):
        self._stop.set()
        if self._socket is not None:
            self._socket.close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._socket = None
        self._thread = None
