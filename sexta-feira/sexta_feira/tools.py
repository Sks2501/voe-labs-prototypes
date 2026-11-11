"""Ferramentas determinísticas explícitas. Texto do modelo nunca chama ferramentas."""
from __future__ import annotations
from datetime import datetime
from .storage import cleaned
from .temperatures import is_temperature_request, read_temperatures, temperature_reply
from .hardware import is_hardware_request, hardware_reply


def execute_tool(name: str, parameters: dict, storage, *, temperature_file=None, hardware_reader=None) -> dict:
    if not isinstance(parameters, dict):
        raise ValueError("parameters deve ser objeto.")
    if name == "server_hardware":
        if parameters:
            raise ValueError("server_hardware não aceita parâmetros.")
        return {**(hardware_reader() if hardware_reader else {"status":"unavailable"}), "executed": True}
    if name == "server_temperatures":
        if parameters:
            raise ValueError("server_temperatures não aceita parâmetros.")
        return {**read_temperatures(temperature_file), "executed": True}
    if name == "system_time":
        if parameters:
            raise ValueError("system_time não aceita parâmetros.")
        return {"datetime": datetime.now().astimezone().isoformat(), "executed": True}
    if name in ("list_tasks", "list_memories"):
        if parameters:
            raise ValueError("Esta ferramenta não aceita parâmetros.")
        return {"items": storage.tasks() if name == "list_tasks" else storage.memories(), "executed": True}
    if name in ("create_task", "save_memory"):
        if set(parameters) != {"content"}:
            raise ValueError("Informe apenas content.")
        content = cleaned(parameters["content"], 480)
        item_id = storage.add_task(content) if name == "create_task" else storage.add_memory(content)
        return {"id": item_id, "executed": True}
    raise ValueError("Ferramenta inexistente ou não autorizada.")


def execute_chat_command(message: str, storage, *, temperature_file=None, hardware_reader=None) -> dict | None:
    """Explicit commands or a narrow read-only temperature request select tools.

    The caller must never pass generated model output to this function.
    """
    if not message.startswith("/"):
        if is_temperature_request(message):
            message = "/temperaturas"
        elif is_hardware_request(message):
            message = "/hardware"
        else:
            return None
    parts = message.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""
    names = {"/hora": "system_time", "/tarefas": "list_tasks", "/memorias": "list_memories",
             "/tarefa": "create_task", "/lembrar": "save_memory",
             "/temperatura": "server_temperatures", "/temperaturas": "server_temperatures", "/sensores": "server_temperatures",
             "/hardware": "server_hardware", "/status": "server_hardware", "/recursos": "server_hardware", "/cpu": "server_hardware", "/ram": "server_hardware"}
    if command not in names:
        raise ValueError("Comando desconhecido. Use /hora, /temperaturas, /tarefas, /memorias, /tarefa texto ou /lembrar texto.")
    name = names[command]
    if name in ("create_task", "save_memory"):
        parameters = {"content": cleaned(argument, 480)}
    else:
        if argument:
            raise ValueError("Este comando não aceita argumentos.")
        parameters = {}
    result = execute_tool(name, parameters, storage, temperature_file=temperature_file, hardware_reader=hardware_reader)
    if name == "server_hardware":
        reply = hardware_reply(result)
    elif name == "server_temperatures":
        reply = temperature_reply(result)
    elif name == "system_time":
        now = datetime.fromisoformat(result["datetime"])
        reply = "Data e hora do servidor: " + now.strftime("%d/%m/%Y às %H:%M:%S") + " (UTC" + now.strftime("%z") + ")."
    elif name == "create_task":
        reply = f"Tarefa #{result['id']} criada: {parameters['content']}"
    elif name == "save_memory":
        reply = f"Memória #{result['id']} salva: {parameters['content']}"
    else:
        items = result["items"]
        if not items:
            reply = "Você ainda não tem " + ("tarefas cadastradas." if name == "list_tasks" else "memórias salvas.")
        else:
            lines = []
            for item in items[:10]:
                state = ("[concluída] " if item["completed"] else "[pendente] ") if name == "list_tasks" else ""
                lines.append(f"#{item['id']} {state}{item['content'][:240]}")
            reply = ("Suas tarefas:\n" if name == "list_tasks" else "Suas memórias:\n") + "\n".join(lines)
            if len(items) > 10:
                reply += f"\nExibindo 10 de {len(items)} registros desta página. Consulte a lista na interface para ver os demais."
    return {"reply": reply, "source": "tool", "generated": False,
            "action_executed": True, "tool": name}
