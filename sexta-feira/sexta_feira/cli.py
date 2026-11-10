"""Comandos do aplicativo local."""
from __future__ import annotations
import argparse
import os
from .settings import DEFAULT_MODEL, MODELS

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sexta-feira",
        description="SEXTA-FEIRA — assistente local baseada no GPT-2 original da OpenAI")
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("serve", help="Iniciar interface web local")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    web.add_argument("--token", default=os.environ.get("SEXTA_ACCESS_TOKEN"))
    download = sub.add_parser("download", help="Baixar pesos oficiais do modelo (uma vez)")
    download.add_argument("--model", choices=list(MODELS), default=DEFAULT_MODEL)
    args = parser.parse_args()
    if args.command == "serve":
        from .server import serve
        serve(args.host, args.port, args.token, args.model)
    elif args.command == "download":
        from .brain import load_model
        print("Baixando/carregando pesos: " + MODELS[args.model])
        load_model(args.model)
        print("Modelo disponível localmente.")
