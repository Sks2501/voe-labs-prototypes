"""Read a bounded server-side snapshot. Never probe the client's hardware or run shell."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import unicodedata

MAX_AGE_SECONDS = 180
LABELS = {"cpu": "Processador", "gpu": "GPU", "memory": "Memória RAM",
          "motherboard": "Placa-mãe", "battery": "Bateria"}
SOURCES = {"storage": "Windows Storage", "acpi": "Windows ACPI"}


def read_temperatures(path: Path | None, *, now: datetime | None = None) -> dict:
    result = {"scope": "server", "status": "unavailable", "observed_at_utc": None,
              "age_seconds": None, "update_interval_seconds": 60, "readings": [],
              "unavailable": [{"component": k, "label": v} for k, v in LABELS.items()]}
    if path is None:
        return result
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            return result
        data = json.loads(raw.decode("utf-8-sig"))
        if data["schema_version"] != 1 or data["scope"] != "server":
            return result
        stamp = datetime.fromisoformat(data["observed_at_utc"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return result
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
        if age < -5:
            return result
        result.update(observed_at_utc=stamp.astimezone(timezone.utc).isoformat(),
                      age_seconds=max(0, round(age)), status="stale" if age > MAX_AGE_SECONDS else "ok")
        if age > MAX_AGE_SECONDS:
            return result  # Old measurements are never presented as current readings.
        readings = data["readings"]
        if not isinstance(readings, list) or len(readings) > 32:
            raise ValueError("Invalid readings")
        for item in readings:
            component, value = item["component"], item["celsius"]
            if component not in SOURCES or type(value) not in (float, int):
                raise ValueError("Unsupported sensor")
            if not math.isfinite(value) or not 0 < value < 150:
                raise ValueError("Invalid temperature")
            index = item["index"]
            if type(index) is not int or not 1 <= index <= 32:
                raise ValueError("Invalid index")
            # Labels and sources come from code, never from untrusted JSON strings.
            result["readings"].append({"component": component,
                "label": ("Disco " if component == "storage" else "Zona térmica ACPI ") + str(index),
                "celsius": round(value, 1), "source": SOURCES[component]})
        if not result["readings"]:
            result["status"] = "unavailable"
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        result.update(status="unavailable", readings=[], observed_at_utc=None, age_seconds=None)
        return result


def temperature_reply(snapshot: dict) -> str:
    if snapshot["status"] != "ok":
        reason = "A última coleta está desatualizada." if snapshot["status"] == "stale" else "Não há leitura de sensores disponível agora."
        return "Temperaturas do servidor onde eu rodo: " + reason + " Não vou estimar valores."
    lines = ["Temperaturas medidas no servidor onde eu rodo:"]
    for reading in snapshot["readings"]:
        value = f"{reading['celsius']:.1f}".replace(".", ",")
        lines.append(f"• {reading['label']}: {value} °C ({reading['source']}).")
    lines.append("CPU, GPU, RAM, placa-mãe e bateria: sensores não disponibilizados nesta configuração.")
    lines.append("A zona ACPI não identifica a temperatura interna da CPU. Não é possível avaliar todos os componentes com essas leituras.")
    stamp = datetime.fromisoformat(snapshot["observed_at_utc"]).astimezone()
    lines.append("Coleta: " + stamp.strftime("%d/%m/%Y %H:%M:%S %z") + f"; há {snapshot['age_seconds']} s. Atualização a cada 60 s.")
    return "\n".join(lines)


def is_temperature_request(message: str) -> bool:
    """Narrow, read-only intent in user input. Model text must never enter here."""
    text = "".join(c for c in unicodedata.normalize("NFKD", message.lower()) if not unicodedata.combining(c)).strip()
    if len(text) > 220 or not re.search(r"\b(temperaturas?|sensores)\b", text):
        return False
    if text.rstrip("?!. ") in ("temperatura", "temperaturas", "sensores"):
        return True
    if re.search(r"\b(explique|exemplo|codigo|programa|escreva|significa|ideal|maxima|limite|ebulicao|clima|cidade)\b", text):
        return False
    return bool(re.match(r"^(?:(?:sexta[ -]feira|amig[oa])[, ]+)?(?:qual|quais|mostr[ae]|me mostr[ae]|verifi(?:que|ca)|consult[ae]|veja|como esta|como estao|temperaturas?)\b", text)
                and re.search(r"\b(vps|servidor|pc|computador|cpu|gpu|processador|hardware|ssd|disco|maquina)\b", text))
