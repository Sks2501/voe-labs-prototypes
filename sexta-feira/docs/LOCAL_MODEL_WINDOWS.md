# Operação do modelo local moderno no Windows

O destino usa `backend: "llama.cpp"` e uma instância Gemma 3 4B IT; GPT-2 e seus pesos originais permanecem disponíveis. O navegador chama a API do Dell; não executa inferência no computador cliente. Veja [artefatos e limites](INFERENCE.md) e [licenças](THIRD_PARTY.md). Não execute o provisionamento inicial para atualizar.

O Python do runtime executa `scripts/prepare_local_model.py RAIZ_PRIVADA` (argumento posicional). O preparo verifica hashes, espaço e marcador de propriedade. Não substitui artefatos divergentes. A ativação exige uma credencial aleatória privada já preparada em `data\inference.token`, sem valor em argumentos/logs. Mantenha DACL privada e acesso LocalService; nunca publique esse arquivo nem o copie para o navegador.

`scripts/activate_local_model.ps1 -RuntimeRoot ... -SourceDirectory ...` aplica uma cópia previamente testada à instalação GPT-2. Valida serviços, porta livre, backup SQLite e fila vazia; preserva configuração e os arquivos relacionados. Recusa um serviço nativo já instalado: não é reinstalação idempotente para manutenção diária.

| Serviço próprio | Função |
| --- | --- |
| `SextaFeiraInference` | WinSW, um único llama-server CPU, loopback autenticado |
| `SextaFeira` | API/interface loopback, cliente do nativo |
| `SextaFeiraTunnel` | Somente o hostname da assistente |

Todos usam LocalService. Inicie modelo → saúde nativa → API → saúde autenticada → túnel próprio. Pare em ordem inversa, aguardando `Stopped` entre etapas. O comando WinSW `stop` pode retornar antes da parada completa. Nunca pare o `Cloudflared` de produção. Não reinicie o Windows neste procedimento.

O runner nativo verifica todos os hashes, exige 5 GiB livres, usa duas threads, prioridade BelowNormal, GPU desativada e um slot. A reserva de memória é preventiva; não representa um limite rígido do Windows. O wrapper recupera após 5 e 30 segundos e depois não reinicia, com reset de falhas em uma hora. Logs rotativos de 1 MiB, três cópias, sem prompts no nativo. A parada sinaliza um evento Windows próprio e encerra somente o filho correspondente; timeout do wrapper de 30 segundos.

Antes de atualizar: backup consistente, versão/configuração, recibos, testes e cópia dos arquivos alterados. Na falha de ativação, o script restaura arquivos/configuração anteriores, para/desabilita o serviço nativo recém-criado e tenta reabrir API/túnel. Não restaura banco antigo por cima de mensagens recentes. Origem das mensagens usa metadados no esquema SQLite 2, sem migração destrutiva.

Para reversão posterior, durante manutenção própria: configure `backend: "gpt2"`, pare o serviço nativo e reinicie a API. Confirme estado/limites GPT-2 e integridade antes de reabrir o acesso. Backups da atualização ficam no runtime privado.

Reboot, falha forçada e rede móvel independente não foram testados. Cloudflare Access não está configurado; o acesso publicado usa HTTPS e autenticação da aplicação.
