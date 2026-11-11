# Origem, atribuições e licenças

- **OpenAI GPT-2:** fonte [openai/gpt-2](https://github.com/openai/gpt-2), licença MIT modificada preservada em `openai-gpt2/LICENSE`. A cópia original e as alterações rastreadas continuam disponíveis. O checkpoint TensorFlow original não foi modificado.
- **llama.cpp:** [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/tree/b12282), licença [MIT](https://github.com/ggml-org/llama.cpp/blob/b12282/LICENSE). O pacote CPU oficial b12282 é instalado separadamente, fora do Git. Preserve os avisos do pacote.
- **Gemma 3 4B IT:** modelo da Google, com [Termos de uso Gemma](https://ai.google.dev/gemma/terms) e [Política de usos proibidos](https://ai.google.dev/gemma/prohibited_use_policy). São pesos abertos sob termos próprios; não os descrevemos como software com licença MIT ou OSI. GGUF quantizado por [ggml-org](https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF). Pesos não estão no repositório nem no ZIP da fonte. Antes de redistribuir pesos ou derivados, cumpra os termos, avisos e requisitos de atribuição aplicáveis.
- **WinSW:** versão 2.12.0, licença MIT. Python e dependências têm suas respectivas licenças; as versões estão nos arquivos de requisitos e nos scripts de provisionamento.

A adoção do Gemma substitui a restrição inicial a um motor exclusivamente OpenAI por autorização posterior do proprietário para usar a alternativa local gratuita. O backend GPT-2 e sua procedência permanecem preservados. Nenhuma dessas organizações endossa esta aplicação.
