"""Ferramentas determinísticas explícitas. Texto do modelo nunca chama ferramentas."""
from __future__ import annotations
from datetime import datetime
import re
import unicodedata
from .storage import cleaned
from .temperatures import is_temperature_request, read_temperatures, temperature_reply
from .hardware import is_hardware_request, hardware_reply
from .web_research import research_request, ResearchUnavailable


def execute_tool(name: str, parameters: dict, storage, *, temperature_file=None, hardware_reader=None, research_reader=None) -> dict:
    if not isinstance(parameters, dict):
        raise ValueError("parameters deve ser objeto.")
    if name == "web_research":
        if set(parameters) not in ({"query"},{"url"}):
            raise ValueError("Informe apenas query ou url.")
        if not research_reader:
            raise ResearchUnavailable("Pesquisa não configurada.")
        return research_reader(**parameters)
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


def _normalized(text: str) -> str:
    return " ".join("".join(char for char in unicodedata.normalize("NFKD",text.casefold())
                            if not unicodedata.combining(char)).split())


def _natural_tool_request(message: str) -> tuple[str, dict] | None:
    """Small Portuguese grammar; quoted instructions and inferred writes are excluded.

    Content following a real imperative remains data. No reference to earlier
    messages is resolved here, and no generated response is accepted as input.
    """
    if not message or message[0] in "\"'`“‘>" or "\n" in message or "\r" in message:
        return None
    text = re.sub(r"^(?:(?:sexta[ -]feira|amig[oa])[,! ]+)?(?:por favor[, ]+)?", "", message,
                  count=1,flags=re.I).strip()
    text = re.sub(r"^(?:quero|preciso)\s+que\s+(?:voc[eê]|vc)\s+", "", text,count=1,flags=re.I)
    normalized = _normalized(text).rstrip(" .!?")
    normalized = re.sub(r"[, ]+por favor$", "", normalized)
    read_requests = {
        "system_time": {"que horas sao", "que hora e", "qual e a hora", "qual a hora",
                        "qual a hora agora", "hora atual", "hora do servidor", "mostre a hora",
                        "mostra a hora", "me diga a hora", "que dia e hoje", "qual a data de hoje",
                        "qual e a data de hoje", "data e hora", "data e hora do servidor",
                        "mostre a data e hora", "mostra a data e hora"},
        "list_tasks": {"minhas tarefas", "mostre minhas tarefas", "mostra minhas tarefas",
                       "mostre as minhas tarefas", "me mostre minhas tarefas", "liste minhas tarefas",
                       "listar minhas tarefas", "consulte minhas tarefas", "ver minhas tarefas",
                       "quais sao minhas tarefas", "quais sao as minhas tarefas", "quais tarefas tenho"},
        "list_memories": {"minhas memorias", "mostre minhas memorias", "mostra minhas memorias",
                          "mostre as minhas memorias", "me mostre minhas memorias", "liste minhas memorias",
                          "listar minhas memorias", "consulte minhas memorias", "ver minhas memorias",
                          "quais sao minhas memorias", "quais sao as minhas memorias",
                          "o que voce tem salvo na memoria", "o que esta salvo na memoria"},
    }
    for name, alternatives in read_requests.items():
        if normalized in alternatives:
            return name, {}
    patterns = (
        ("create_task", r"(?:crie|cria|adicione|adiciona|cadastre|cadastra|registre|registra|anote|anota)\s+(?:(?:uma|a)\s+)?(?:nova\s+)?tarefa(?:\s*:\s*|\s+(?:para\s+)?)(?P<content>.+)"),
        ("save_memory", r"(?:lembre|memorize)\s+que\s+(?P<content>.+)"),
        ("save_memory", r"(?:salve|guarde|registre|anote)\s+(?:(?:uma|esta|essa)\s+)?mem[oó]ria(?:\s*:\s*|\s+)(?P<content>.+)"),
        ("save_memory", r"(?:salve|guarde|registre)\s+(?:na|minha|em minha)\s+mem[oó]ria\s*:\s*(?P<content>.+)"),
    )
    for name, pattern in patterns:
        match = re.fullmatch(pattern,text,re.I)
        if not match:
            continue
        content = match["content"].strip()
        intent = _normalized(content)
        if (re.match(r"^(?:se|caso|talvez|hipoteticamente|suponha|por exemplo|como exemplo|de exemplo)\b",intent)
                or re.search(r"\bnao\s+(?:crie|criar|salve|salvar|registre|registrar|guarde|guardar|memorize|memorizar|anote|anotar)\b",intent)
                or re.search(r"\b(?:e|tambem|depois)\s+(?:crie|cria|salve|salva|registre|registra|guarde|guarda|adicione|adiciona)\b",intent)):
            return None
        return name, {"content":cleaned(content,480)}
    if is_temperature_request(text):
        return "server_temperatures", {}
    if is_hardware_request(text):
        return "server_hardware", {}
    return None


def execute_chat_command(message: str, storage, *, temperature_file=None, hardware_reader=None, research_reader=None,
                         auto_research: bool = True) -> dict | None:
    """Explicit user commands and narrow local intents select deterministic tools.

    The caller must never pass generated model output to this function.
    """
    if not isinstance(message,str):
        raise ValueError("message deve ser texto.")
    if type(auto_research) is not bool:
        raise ValueError("auto_research deve ser booleano.")
    message = message.strip()
    names = {"/hora": "system_time", "/tarefas": "list_tasks", "/memorias": "list_memories",
             "/tarefa": "create_task", "/lembrar": "save_memory",
             "/temperatura": "server_temperatures", "/temperaturas": "server_temperatures", "/sensores": "server_temperatures",
             "/hardware": "server_hardware", "/status": "server_hardware", "/recursos": "server_hardware", "/cpu": "server_hardware", "/ram": "server_hardware"}
    selected = _natural_tool_request(message) if not message.startswith("/") else None
    if selected is None and message.startswith("/"):
        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""
        if command in names:
            name = names[command]
            if name in ("create_task", "save_memory"):
                selected = name, {"content":cleaned(argument,480)}
            elif argument:
                raise ValueError("Este comando não aceita argumentos.")
            else:
                selected = name, {}
    if selected is None:
        request = research_request(message,auto=auto_research)
        if request is not None:
            return execute_tool("web_research",request,storage,research_reader=research_reader)
        if message.startswith("/"):
            raise ValueError("Comando desconhecido. Você pode pedir: Que horas são? Mostre minhas tarefas. Crie uma tarefa: texto. Lembre que texto.")
        return None
    name, parameters = selected
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
