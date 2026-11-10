# SEXTA-FEIRA — OpenAI GPT-2 local para Windows

Assistente experimental pessoal, gratuita, sem API paga, sem Ollama e sem GPU obrigatória.
O núcleo original do repositório [openai/gpt-2](https://github.com/openai/gpt-2) está preservado na pasta `openai-gpt2/`, com otimizações pontuais no cache do tokenizador e no exemplo de geração por CPU.

O aplicativo `sexta_feira/` executa **os mesmos pesos GPT-2** disponibilizados pela OpenAI, através de uma adaptação em PyTorch/Transformers. Isso evita a exigência do TensorFlow 1.12 original, que não é adequado para Python moderno no Windows. Esta adaptação **não executa diretamente o código TensorFlow de `openai-gpt2/src/model.py`**: os arquivos originais estão incluídos para modificações, estudo e preservação da procedência.

**Limitação:** GPT-2 é um modelo de 2019 de previsão de texto, não um chatbot treinado para seguir instruções. Pode produzir respostas incorretas, incoerentes, em inglês ou não seguir o papel de assistente. Modificar código não o torna equivalente ao ChatGPT. O aplicativo não controla o sistema operacional, não acessa dados privados automaticamente e não tem comandos de shell.

## Requisitos

- Windows 10 ou 11, 64 bits, Python 3.11 64 bits, conexão apenas para instalação.
- CPU Intel i5-4570 e 12 GB de RAM são suficientes para experimentar com `small` (124M). O desempenho real varia.
- Aproximadamente 5 GB ou mais livres para Python, PyTorch, bibliotecas e modelo.
- Git opcional se usar o ZIP do GitHub.

## Instalação automática no Windows

1. Instale [Python 3.11 x64](https://www.python.org/downloads/) com o Python Launcher.
2. Abra a pasta `sexta-feira` que contém este README.
3. Execute `instalar_windows.bat`. Ele cria o ambiente virtual, instala PyTorch CPU e Transformers e baixa os pesos oficiais convertidos do GPT-2 small.
4. Execute `iniciar_windows.bat`. O programa exibe o endereço e um token único de acesso.
5. Abra `http://127.0.0.1:8765` no navegador, cole o token e clique em Conectar.
6. Converse, salve memórias e tarefas. Para desligar, use Ctrl+C na janela do servidor.

Os pesos são baixados uma única vez do identificador `openai-community/gpt2` (checkpoint GPT-2 original convertido ao formato Transformers). Após instalar, `iniciar_windows.bat` define `SEXTA_OFFLINE=1` para impedir tentativas de download do modelo.

## Executar testes

Com a instalação concluída, execute `TESTES.bat` para testar armazenamento e rotas HTTP. O teste de inferência completa requer carregar o modelo e não é automatizado aqui.

## Acesso pelo celular

O servidor por padrão aceita exclusivamente conexões do próprio computador (`127.0.0.1`). O endereço do navegador **não funciona no celular** neste modo. Existe um modo de rede local por `python -m sexta_feira serve --host 0.0.0.0 --token ...`, porém o HTTP não criptografa tráfego, então não exponha na Internet. Para uso por celular, prefira rede privada com túnel autenticado e TLS, configurado pelo proprietário. Não há exposição pública automática.

## Alterar tamanho do cérebro

`small` (124M) é o padrão; `medium` (355M) e `large` (774M) podem ser selecionados usando o CLI `download --model medium` e depois `serve --model medium`, mas aumentam consumo e lentidão. O XL 1558M está no repositório original, mas não é selecionável no adaptador por causa das limitações deste PC.

## Licença, direitos e identificação

- Código GPT-2 original e pesos: licença modificada MIT da OpenAI, em `openai-gpt2/LICENSE`. Preserve as atribuições e a indicação de texto gerado por IA.
- O restante do código de adaptação da SEXTA-FEIRA pode ser editado e distribuído, respeitando a licença acima.
- SEXTA-FEIRA é uma personalização **independente**. Não é produto oficial da OpenAI, nem uma cópia do ChatGPT/Claude. O projeto não contém código privado dessas empresas.

## Privacidade

Mensagens, memórias e tarefas ficam em SQLite no diretório `%LOCALAPPDATA%\SextaFeira` (Windows) ou `~/.sexta-feira` em outros sistemas.
O token é apresentado a cada inicialização, não é salvo automaticamente no navegador, e não há API remota de IA. Não exponha a porta 8765 na Internet.
