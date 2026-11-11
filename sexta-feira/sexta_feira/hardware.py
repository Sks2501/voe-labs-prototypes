"""Owner-readable operational data. No process IDs, network inventory or secrets."""
from __future__ import annotations
import re
import unicodedata

FIELDS = ("sampled_at_utc", "cpu_model", "cpu_logical", "system_cpu_percent",
          "ram_total_bytes", "ram_available_bytes", "ram_used_percent", "process_rss_bytes",
          "inference_process_rss_bytes", "api_process_rss_bytes", "disk_free_bytes", "disk_total_bytes")


def hardware_snapshot(metrics: dict, temperatures: dict) -> dict:
    return {"scope": "server", "resources": {key: metrics[key] for key in FIELDS if key in metrics},
            "temperatures": temperatures}


def hardware_reply(snapshot: dict) -> str:
    if snapshot.get("scope") != "server":
        return "Não há leitura de hardware do servidor disponível agora."
    r = snapshot["resources"]
    lines = ["Recursos medidos no servidor onde eu rodo:"]
    if r.get("cpu_model"):
        lines.append("• CPU: " + r["cpu_model"] + f" ({r['cpu_logical']} processadores lógicos).")
    percent = r.get("system_cpu_percent")
    lines.append("• Uso total de CPU: " + (f"{percent:.1f}%" if percent is not None else "coletando; consulte novamente em alguns segundos") + ".")
    total, available = r.get("ram_total_bytes"), r.get("ram_available_bytes")
    if total and available is not None:
        lines.append(f"• RAM: {(total-available)/2**30:.2f} GiB usados de {total/2**30:.2f} GiB; {available/2**30:.2f} GiB disponíveis.")
    if "process_rss_bytes" in r:
        lines.append(f"• RAM da IA + API: {r['process_rss_bytes']/2**30:.2f} GiB.")
    if r.get("disk_total_bytes"):
        lines.append(f"• Disco: {r['disk_free_bytes']/2**30:.1f} GiB livres de {r['disk_total_bytes']/2**30:.1f} GiB.")
    from .temperatures import temperature_reply
    lines.append(temperature_reply(snapshot["temperatures"]))
    lines.append("Uso em %/GiB e temperatura em °C são medidas diferentes. Nenhuma avaliação geral de segurança térmica foi feita.")
    return "\n".join(lines)


def is_hardware_request(message: str) -> bool:
    text = "".join(c for c in unicodedata.normalize("NFKD",message.lower()) if not unicodedata.combining(c)).strip()
    if len(text) > 220 or re.search(r"\b(explique|exemplo|codigo|escreva|significa|ideal|maxima|limite)\b",text):
        return False
    target = re.search(r"\b(vps|servidor|cpu|ram|disco|hardware|maquina|pc)\b",text)
    return bool(target and re.match(r"^(?:(?:sexta[ -]feira|amig[oa])[, ]+)?(?:como esta|como estao|qual|quais|mostr[ae]|me mostr[ae]|verifi(?:que|ca)|consult[ae]|veja|uso|status|estado|recursos|desempenho)\b",text))
