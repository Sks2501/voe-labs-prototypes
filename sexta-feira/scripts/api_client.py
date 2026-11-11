"""Small authenticated API client: loopback HTTPS/HTTP, or encrypted SSH stdio.

No inference provider, DNS, public port, credential argument, or SSH forwarding.
Private JSON configuration supplies token_file and optional SSH connection paths.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def call_http(base_url, frame):
    origin = urllib.parse.urlsplit(base_url)
    if (origin.username or origin.password or origin.path not in ("", "/")
            or origin.query or origin.fragment or origin.scheme not in ("http", "https")
            or (origin.scheme == "http" and origin.hostname not in ("127.0.0.1", "localhost", "::1"))):
        raise ValueError("API requires loopback HTTP or verified HTTPS")
    path = frame["path"]
    if (not isinstance(path, str) or not path.startswith("/api/v1/")
            or any(ord(c) < 32 for c in path) or "#" in path or len(path) > 1024):
        raise ValueError("Invalid API path")
    method = frame["method"]
    if method not in ("GET", "POST", "PATCH", "DELETE"):
        raise ValueError("Invalid HTTP method")
    token = frame["token"]
    if not isinstance(token, str) or not 32 <= len(token) <= 512 or any(c.isspace() for c in token):
        raise ValueError("Invalid private credential")
    body = frame.get("body")
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if data is not None and (not isinstance(body, dict) or len(data) > 8192):
        raise ValueError("JSON object body must fit 8192 bytes")
    request = urllib.request.Request(base_url.rstrip("/") + path, method=method, data=data,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                 "Content-Type": "application/json; charset=utf-8", "User-Agent": "SextaFeira-APIClient/1.0"})
    # Do not follow redirects carrying an Authorization header to another origin.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        response = urllib.request.build_opener(NoRedirect()).open(request, timeout=90)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        payload = response.read(6 * 1024 * 1024 + 1)
        if len(payload) > 6 * 1024 * 1024:
            raise ValueError("API response exceeds client size limit")
        return {"status": response.code, "body": json.loads(payload)}


def request(config, method, path, body=None):
    token = Path(config["token_file"]).read_text(encoding="utf-8-sig").strip()
    frame = {"method": method, "path": "/api/v1/" + path.lstrip("/"), "body": body, "token": token}
    if config.get("transport", "http") == "http":
        return call_http(config.get("base_url", "http://127.0.0.1:8765"), frame)
    if config["transport"] != "ssh":
        raise ValueError("Unsupported API transport")
    # SSH runs only this fixed client command. Request bodies and credentials go
    # through encrypted stdin, never shell interpolation or process arguments.
    remote_command = subprocess.list2cmdline([config["remote_python"], "-I", "-B",
        config["remote_client"], "--stdio", "--base-url", "http://127.0.0.1:8765"])
    known_hosts = str(Path(config["known_hosts"]).resolve()).replace("\\", "/")
    args = [config.get("ssh_executable", "ssh"), "-T", "-i", config["ssh_key"],
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", 'UserKnownHostsFile="' + known_hosts + '"', "-o", "ConnectTimeout=10",
            config["ssh_host"], remote_command]
    completed = subprocess.run(args, input=json.dumps(frame, ensure_ascii=False).encode("utf-8"),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=110,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        raise RuntimeError("Private SSH API transport failed; check key, host fingerprint and connection")
    return json.loads(completed.stdout.decode("utf-8-sig"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--stdio", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("health")
    chat = commands.add_parser("chat")
    chat.add_argument("message", nargs="?", help="Omit to read message from stdin")
    raw = commands.add_parser("request")
    raw.add_argument("method", choices=("GET", "POST", "PATCH", "DELETE"))
    raw.add_argument("path", help="Path relative to /api/v1, for example tasks")
    raw.add_argument("--json-file", type=Path, help="JSON object body, never credentials")
    args = parser.parse_args()
    if args.stdio:
        frame_bytes = sys.stdin.buffer.read(16385)
        if len(frame_bytes) > 16384:
            raise ValueError("API transport frame exceeds limit")
        result = call_http(args.base_url, json.loads(frame_bytes.decode("utf-8")))
    else:
        if not args.config or not args.command:
            parser.error("--config and a command are required")
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        if args.command == "health":
            result = request(config, "GET", "health")
        elif args.command == "chat":
            message = args.message if args.message is not None else sys.stdin.read()
            result = request(config, "POST", "conversations", {"message": message})
        else:
            body = json.loads(args.json_file.read_text(encoding="utf-8-sig")) if args.json_file else None
            result = request(config, args.method, args.path, body)
    sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0 if 200 <= result["status"] < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
