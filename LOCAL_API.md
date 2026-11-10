# GPT-2 original da OpenAI: execução local otimizada para CPU

Este repositório preserva os arquivos do projeto original [`openai/gpt-2`](https://github.com/openai/gpt-2), incluindo a licença original e o código TensorFlow. A adição `src/local_api.py` fornece uma API HTTP local com uma implementação de inferência atualizada para Windows, usando os pesos **GPT-2 treinados pela OpenAI** publicados como `openai-community/gpt2` (124 milhões de parâmetros). Não é o código-fonte do ChatGPT e não usa serviços pagos.

## Requisitos

- Windows 10/11 64-bit, Python 3.11, conexão à internet somente para instalação e primeiro download do modelo
- Recomendação: 8 GB de RAM ou mais; CPUs antigas operam lentamente
- Sem chave de API, sem Ollama e sem placa de vídeo dedicada

## Executar no Windows

Na raiz do repositório, execute `scripts\start_windows.bat`. O script cria um ambiente virtual, instala PyTorch somente-CPU e dependências e inicia `http://127.0.0.1:8765`. O primeiro início baixa os pesos gratuitos de um espelho público; os próximos usam cache. Para impedir novos downloads depois da primeira execução, rode `python src\local_api.py --threads 2 --offline` no ambiente virtual.

## Testar

Execute `python -m unittest discover -s tests -v` na raiz do projeto. Os testes de HTTP usam um modelo fictício e não exigem baixar os pesos.

## Exemplo de requisição no PowerShell

```powershell
$body = @{messages = @(@{role = 'user'; content = 'Olá, GPT-2!' }); max_tokens = 48} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/v1/chat/completions' -Method Post -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

A API implementa `GET /health`, `GET /v1/models` e `POST /v1/chat/completions`. O endereço aceita apenas conexões locais, não exponha a porta à internet. Não existe autenticação porque a escuta está limitada a `127.0.0.1`. Não aceite conexões de rede sem adicionar autenticação e TLS.

## Modificações e limites

- Mantidos todos os arquivos e nomes originais do GPT-2, inclusive `src/model.py`, `src/sample.py`, `src/encoder.py` e `LICENSE`.
- O executável legado `src/interactive_conditional_samples.py` foi ajustado para controlar threads do TensorFlow em CPU; exige o ambiente legado compatível com TensorFlow 1.x.
- O motor moderno `src/local_api.py` utiliza Transformers/PyTorch apenas para executar os pesos originais com software compatível com Windows atual. A API é local, não usa o serviço OpenAI API.
- GPT-2 é um modelo de **completar texto**, não um assistente instruído como o ChatGPT; pode responder incorretamente e tem compreensão limitada de português e de comandos. As modificações não alteram esse limite fundamental.
- Não altere nem publique dados pessoais ou chaves; a pasta `.venv` e caches de pesos são ignorados pelo Git.

## Direitos autorais

O código derivado mantém a licença modificada do MIT da OpenAI em `LICENSE`. O conteúdo gerado pelo GPT-2 deve ser identificado conforme a licença do projeto original.