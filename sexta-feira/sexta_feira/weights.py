"""Official OpenAI GPT-2 checkpoint download and minimal read-only TF bundle reader.

Only the uncompressed, single-shard FLOAT32 TensorBundle format used by the
published GPT-2 checkpoint is supported. No pickle, executable graph or model
code is deserialized. The original TensorFlow files are retained unchanged.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import urllib.request
import uuid

BASE_URL = "https://openaipublic.blob.core.windows.net/gpt-2/models/"
FILES = ("checkpoint", "encoder.json", "hparams.json", "model.ckpt.data-00000-of-00001",
         "model.ckpt.index", "model.ckpt.meta", "vocab.bpe")
# Content-MD5 metadata observed on the OpenAI HTTPS origin, 2026-11-10.
# MD5 checks transport corruption; HTTPS establishes source identity. The local
# manifest uses SHA-256 and is checked before every model load, entirely offline.
OFFICIAL_124M = {
    "checkpoint": (77, "ygNo/NPEwamaykJRHQwfEg=="),
    "encoder.json": (1042301, "3/7CWomLH15Wm+xN/9flwA=="),
    "hparams.json": (90, "/Qhc3b88bSVt4wEYghbfwQ=="),
    "model.ckpt.data-00000-of-00001": (497759232, "9Iuc8aUlpgO+UiWPab+RYg=="),
    "model.ckpt.index": (5215, "Ejvl7LJGEwsdHlKvVYQU7Q=="),
    "model.ckpt.meta": (471155, "zNkmawXQ+WDiQSEAv0/FWg=="),
    "vocab.bpe": (456318, "daN3U916KKLF34DCi/BuTg=="),
}
# SHA-256 measured from the unchanged HTTPS downloads on 2026-11-10, then
# pinned here. These are project-verified hashes, not an OpenAI signature.
OFFICIAL_124M_SHA256 = {
    "checkpoint": "dd1b025d2e155283f5e300ce95bf6d5b6bc0f7fe010db73daa6975eb896ab9cb",
    "encoder.json": "196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783",
    "hparams.json": "d9d56e4121c427164e0c55c6f03c08e1daf9002b9b672825112d19097b680318",
    "model.ckpt.data-00000-of-00001": "2060c885360cc0cf41d7a6dbc4d24b5127aae20260c8b5ae521b5a6578407118",
    "model.ckpt.index": "71916f763f9746f9b2a06b12d91996cf1084ae008d0424543d39391c5f2dc687",
    "model.ckpt.meta": "4668c448fa11531fd6700460487f73e82d3272960cea942252f8744bf225c77b",
    "vocab.bpe": "1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5",
}


def digest_file(path: Path) -> tuple[str, str]:
    sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(chunk)
            md5.update(chunk)
    return sha.hexdigest(), base64.b64encode(md5.digest()).decode("ascii")


def download_weights(models_dir: Path, model_name: str = "124M") -> dict:
    """Idempotent download; never replaces an existing mismatched checkpoint."""
    if model_name not in ("124M", "355M"):
        raise ValueError("Only 124M and explicitly selected 355M are supported")
    target = Path(models_dir) / model_name
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"source": BASE_URL + model_name + "/", "model": model_name,
                "format": "OpenAI original TensorFlow checkpoint", "files": {}}
    for name in FILES:
        expected = OFFICIAL_124M.get(name) if model_name == "124M" else None
        final = target / name
        url = BASE_URL + model_name + "/" + name
        if expected is None:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
                expected = (int(response.headers["Content-Length"]), response.headers["Content-MD5"])
        size, md5_expected = expected
        if final.exists():
            sha, md5 = digest_file(final)
            if final.stat().st_size != size or md5 != md5_expected:
                raise ValueError("Existing weight file failed integrity; preserved: " + name)
        else:
            if shutil.disk_usage(target).free < size + 512 * 1024 * 1024:
                raise OSError("Insufficient free disk space; reserve 512 MiB after download")
            part = target / (name + ".part." + uuid.uuid4().hex)
            # Unique exclusive partials allow retry without deleting failed data.
            with part.open("xb") as sink:
                with urllib.request.urlopen(url, timeout=60) as response:
                    if response.geturl().split("/")[2] != "openaipublic.blob.core.windows.net":
                        raise ValueError("Unexpected model download redirect")
                    if int(response.headers.get("Content-Length", "-1")) != size:
                        raise ValueError("Unexpected model download Content-Length")
                    received = 0
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        received += len(chunk)
                        if received > size:
                            raise ValueError("Model download exceeded its expected size")
                        if shutil.disk_usage(target).free < len(chunk) + 512 * 1024 * 1024:
                            raise OSError("Disk reserve reached during download; partial preserved")
                        sink.write(chunk)
                sink.flush()
                os.fsync(sink.fileno())
            sha, md5 = digest_file(part)
            if part.stat().st_size != size or md5 != md5_expected:
                raise ValueError("Downloaded weight failed integrity; .part retained for diagnosis")
            if model_name == "124M" and sha != OFFICIAL_124M_SHA256[name]:
                raise ValueError("Official 124M SHA-256 differs from pinned project baseline: " + name)
            part.rename(final)
        if model_name == "124M" and sha != OFFICIAL_124M_SHA256[name]:
            raise ValueError("Official 124M SHA-256 differs from pinned project baseline: " + name)
        manifest["files"][name] = {"size": size, "sha256": sha, "source_md5": md5_expected}
    temporary = target / "integrity.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target / "integrity.json")
    return manifest


def verify_weights(directory: Path) -> dict:
    manifest = json.loads((directory / "integrity.json").read_text(encoding="utf-8"))
    if manifest.get("source") != BASE_URL + directory.name + "/":
        raise ValueError("Unexpected checkpoint provenance")
    for name in FILES:
        metadata = manifest["files"][name]
        path = directory / name
        if path.stat().st_size != metadata["size"]:
            raise ValueError("Checkpoint size mismatch: " + name)
        sha, md5 = digest_file(path)
        if sha != metadata["sha256"]:
            raise ValueError("Checkpoint SHA-256 mismatch: " + name)
        if directory.name == "124M" and sha != OFFICIAL_124M_SHA256[name]:
            raise ValueError("Checkpoint differs from pinned project SHA-256: " + name)
        if directory.name == "124M" and (path.stat().st_size, md5) != OFFICIAL_124M[name]:
            raise ValueError("Checkpoint differs from official OpenAI blob metadata: " + name)
    return manifest


def _varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError("Truncated checkpoint integer")
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError("Invalid checkpoint integer")


def _fields(data: bytes):
    pos = 0
    while pos < len(data):
        tag, pos = _varint(data, pos)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire == 2:
            size, pos = _varint(data, pos)
            value, pos = data[pos:pos + size], pos + size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value, pos = int.from_bytes(data[pos:pos + size], "little"), pos + size
        else:
            raise ValueError("Unsupported checkpoint protobuf field")
        if pos > len(data):
            raise ValueError("Truncated checkpoint protobuf")
        yield field, value


def _entries(block: bytes):
    if len(block) < 4:
        raise ValueError("Invalid checkpoint table block")
    restarts = struct.unpack_from("<I", block, len(block) - 4)[0]
    end, pos, previous = len(block) - 4 * (restarts + 1), 0, b""
    while pos < end:
        shared, pos = _varint(block, pos)
        unshared, pos = _varint(block, pos)
        size, pos = _varint(block, pos)
        if shared > len(previous) or pos + unshared + size > end:
            raise ValueError("Corrupt checkpoint table entry")
        key = previous[:shared] + block[pos:pos + unshared]
        pos += unshared
        value, pos = block[pos:pos + size], pos + size
        previous = key
        yield key, value


def _block(data: bytes, handle: bytes) -> bytes:
    offset, pos = _varint(handle, 0)
    size, _ = _varint(handle, pos)
    if offset + size + 5 > len(data):
        raise ValueError("Checkpoint table offset outside file")
    if data[offset + size] != 0:
        raise ValueError("Only uncompressed original OpenAI checkpoint tables are supported")
    return data[offset:offset + size]


def checkpoint_entries(index_path: Path) -> dict:
    data = index_path.read_bytes()
    if len(data) < 48 or data[-8:] != bytes.fromhex("57fb808b247547db"):
        raise ValueError("Invalid TensorFlow checkpoint table magic")
    footer = data[-48:-8]
    _, pos = _varint(footer, 0)
    _, pos = _varint(footer, pos)
    entries = {}
    for _, handle in _entries(_block(data, footer[pos:])):
        for name, raw in _entries(_block(data, handle)):
            if not name:
                continue
            item = dict(_fields(raw))
            dimensions = []
            for field, dimension in _fields(item.get(2, b"")):
                if field == 2:
                    dimensions.append(dict(_fields(dimension)).get(1, 0))
            if item.get(1) != 1 or item.get(3, 0) != 0:
                raise ValueError("Only single-shard FLOAT32 GPT-2 weights are supported")
            entries[name.decode("utf-8")] = {
                "shape": dimensions, "offset": item.get(4, 0), "size": item.get(5, 0)}
    if not entries:
        raise ValueError("Checkpoint has no model tensors")
    return entries


def load_checkpoint(directory: Path) -> dict:
    """Load raw float arrays after complete file integrity validation."""
    import numpy as np
    verify_weights(directory)
    entries = checkpoint_entries(directory / "model.ckpt.index")
    arrays = {}
    with (directory / "model.ckpt.data-00000-of-00001").open("rb") as source:
        total_size = os.fstat(source.fileno()).st_size
        for name, entry in entries.items():
            shape, offset, size = entry["shape"], entry["offset"], entry["size"]
            if not name.startswith("model/") or any(n < 1 for n in shape):
                raise ValueError("Unexpected GPT-2 tensor name or shape")
            count = 1
            for dimension in shape:
                count *= dimension
            if count * 4 != size or offset < 0 or offset + size > total_size:
                raise ValueError("Invalid GPT-2 tensor bounds")
            source.seek(offset)
            arrays[name] = np.fromfile(source, dtype="<f4", count=count).reshape(shape)
    return arrays


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download and verify original OpenAI GPT-2 weights")
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--model", choices=("124M", "355M"), default="124M")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify_weights(args.models_dir / args.model) if args.verify else download_weights(args.models_dir, args.model)
    print(json.dumps({"model": result["model"], "verified_files": len(result["files"])}))
