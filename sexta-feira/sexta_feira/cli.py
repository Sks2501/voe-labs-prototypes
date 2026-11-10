"""Comandos locais; nenhum segredo é exibido ou incluído na linha de comando."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets


def initialize() -> Path:
    from .settings import DATA_DIR, TOKEN_FILE
    from .storage import Storage
    from .windows_security import protect_data_directory
    if TOKEN_FILE.parent.resolve() != DATA_DIR.resolve():
        raise ValueError("O arquivo de autenticação deve ficar dentro da pasta de dados protegida.")
    protect_data_directory(DATA_DIR)
    Storage()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if len(TOKEN_FILE.read_text(encoding="utf-8").strip()) < 32:
            raise ValueError("Arquivo de autenticação inválido; conteúdo existente preservado.")
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            target.write(secrets.token_urlsafe(32) + "\n")
    return TOKEN_FILE

def main() -> None:
    from .settings import DEFAULT_MODEL, MODELS, MODEL_DIR, TOKEN_FILE, DATA_DIR
    parser = argparse.ArgumentParser(
        prog="sexta-feira",
        description="SEXTA-FEIRA — assistente local baseada no GPT-2 original da OpenAI")
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("serve", help="Iniciar interface web local")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    web.add_argument("--token-file", type=Path, default=TOKEN_FILE)
    download = sub.add_parser("download", help="Baixar pesos oficiais do modelo (uma vez)")
    download.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    download.add_argument("--models-dir", type=Path, default=MODEL_DIR)
    verify = sub.add_parser("verify-model", help="Validar integridade offline dos pesos")
    verify.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    verify.add_argument("--models-dir", type=Path, default=MODEL_DIR)
    sub.add_parser("init", help="Inicializar SQLite e segredo local sem exibi-lo")
    sub.add_parser("diagnose", help="Exibir métricas locais sem dados pessoais")
    args = parser.parse_args()
    if args.command == "serve":
        from .observability import configure_logging
        from .server import serve
        if not 1 <= args.port <= 65535:
            parser.error("Porta deve estar entre 1 e 65535.")
        token = args.token_file.read_text(encoding="utf-8").strip()
        if len(token) < 32:
            parser.error("Execute init e configure um arquivo de autenticação privado.")
        configure_logging(DATA_DIR)
        serve(args.host, args.port, token, args.model)
    elif args.command in ("download", "verify-model"):
        from .weights import download_weights, verify_weights
        result = (download_weights(args.models_dir, MODELS[args.model])
                  if args.command == "download" else
                  verify_weights(args.models_dir / MODELS[args.model]))
        print(json.dumps({"model": result["model"], "verified_files": len(result["files"])}))
    elif args.command == "init":
        path = initialize()
        print("SQLite inicializado. Segredo preservado em arquivo privado: " + str(path))
    elif args.command == "diagnose":
        from .observability import resource_snapshot
        print(json.dumps(resource_snapshot(DATA_DIR if DATA_DIR.exists() else Path.cwd()), indent=2))
