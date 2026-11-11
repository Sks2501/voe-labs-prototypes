"""Pinned, streaming downloads for the authorized no-fee local model upgrade."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request
import uuid
import zipfile

ARTIFACTS = (
    ("llama-b12282-bin-win-cpu-x64.zip", "https://github.com/ggml-org/llama.cpp/releases/download/b12282/llama-b12282-bin-win-cpu-x64.zip",
     25058018, "582a5da726b30e0b9e801b4ebd1b85cbe023ca266bdebf6a9d55426c85e57463"),
    ("gemma-3-4b-it-Q4_K_M.gguf", "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/d0976223747697cb51e056d85c532013931fe52e/gemma-3-4b-it-Q4_K_M.gguf",
     2489757856, "882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863"),
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(runtime):
    runtime = Path(runtime).resolve()
    if not (runtime / ".sexta-runtime").is_file():
        raise ValueError("An identified private SEXTA-FEIRA runtime is required")
    destination = runtime / "local-model"
    if destination.is_symlink():
        raise ValueError("Symlink destination refused")
    destination.mkdir(exist_ok=True)
    receipts = []
    for name, url, size, expected in ARTIFACTS:
        target = destination / name
        if target.exists():
            if target.stat().st_size != size or sha256(target) != expected:
                raise ValueError("Existing artifact differs; preserved: " + name)
        else:
            if shutil.disk_usage(destination).free < size + 4 * 1024**3:
                raise OSError("Keep at least 4 GiB free after preparation")
            part = destination / (name + ".part." + uuid.uuid4().hex)
            count = 0
            digest = hashlib.sha256()
            last = time.monotonic()
            request = urllib.request.Request(url, headers={"User-Agent": "SextaFeira-LocalModel/1.0"})
            print("Downloading pinned artifact: " + name, flush=True)
            with urllib.request.urlopen(request, timeout=60) as response, part.open("xb") as output:
                if not response.geturl().startswith("https://"):
                    raise ValueError("Unencrypted artifact redirect refused")
                if int(response.headers.get("Content-Length", size)) != size:
                    raise ValueError("Unexpected artifact size")
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    count += len(block)
                    if count > size or shutil.disk_usage(destination).free < 4 * 1024**3:
                        raise OSError("Artifact size/disk reserve exceeded; partial preserved")
                    output.write(block)
                    digest.update(block)
                    if time.monotonic() - last >= 8:
                        print(f"{name}: {count // (1024**2)}/{size // (1024**2)} MiB", flush=True)
                        last = time.monotonic()
                output.flush()
                os.fsync(output.fileno())
            if count != size or digest.hexdigest() != expected:
                raise ValueError("Artifact integrity failed; partial preserved")
            part.rename(target)
        receipts.append({"file": name, "source": url, "bytes": size, "sha256": expected})
        print("Verified: " + name, flush=True)
    binary_directory = destination / "llama-b12282"
    if not binary_directory.exists():
        staging = destination / ("llama-staging-" + uuid.uuid4().hex)
        staging.mkdir()
        with zipfile.ZipFile(destination / ARTIFACTS[0][0]) as archive:
            for entry in archive.infolist():
                entry_path = (staging / entry.filename).resolve()
                if not entry_path.is_relative_to(staging.resolve()) or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError("Unsafe archive entry")
            archive.extractall(staging)
        (staging / ".sexta-llama.json").write_text(json.dumps({"release":"b12282", "files":{
            str(p.relative_to(staging)):sha256(p) for p in staging.rglob("*") if p.is_file()}}), encoding="utf-8")
        staging.rename(binary_directory)
    receipt = json.loads((binary_directory / ".sexta-llama.json").read_text())
    for name, expected in receipt["files"].items():
        path = (binary_directory / name).resolve()
        if not path.is_relative_to(binary_directory.resolve()) or sha256(path) != expected:
            raise ValueError("Installed llama.cpp integrity mismatch")
    (destination / "artifacts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print("Local model artifacts ready; no running model/service was replaced.", flush=True)


if __name__ == "__main__":
    prepare(sys.argv[1])
