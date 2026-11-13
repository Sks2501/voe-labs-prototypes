# Organização e manutenção do servidor

A instalação separa código, runtime, dados pessoais, modelos, serviços, logs e artefatos antigos. O inventário privado fica em `maintenance/server-inventory.json`; o índice operacional fica em `maintenance/OPERACAO.md`, dentro do runtime identificado. Esses arquivos não são publicados no GitHub nem servidos pela API.

| Local no runtime | Finalidade |
|---|---|
| `data` | SQLite, credenciais privadas e distribuição Android |
| `local-model`, `models` | Modelos em uso e base histórica preservada |
| `venv` | Ambiente Python da aplicação |
| `service`, `cloudflare` | Serviços e túnel próprios |
| `logs`, `data/logs` | Logs operacionais com rotação |
| `sensors`, `sensor-provider` | Coletor isolado e biblioteca de sensores |
| `updates` | Estágios e backups de atualização/reversão |
| `maintenance` | Planos, inventário e verificações privadas |
| `archive` | Cópias antigas de instaladores, com caminho e hash de origem |

## Arquivar cópias antigas de instaladores

O script `scripts/organize-runtime.ps1` aceita somente dez nomes fixos de ZIP/APK antigos no diretório irmão `SextaFeiraDiagnostics`. Exige o marcador do runtime vinculado ao código atual, recusa pontos de redirecionamento, caminhos fora dos diretórios próprios, destino já ocupado e hashes alterados. Os arquivos devem ter ao menos uma hora de idade ao gerar o plano.

```powershell
# PowerShell administrativo no servidor, a partir da pasta do projeto.
.\scripts\organize-runtime.ps1 -RuntimeRoot C:\SextaFeiraRuntime -Action Plan

# Use exatamente o caminho privado do plano retornado; examine os itens antes.
.\scripts\organize-runtime.ps1 -RuntimeRoot C:\SextaFeiraRuntime -Action Apply -PlanFile 'CAMINHO_PRIVADO_DO_PLANO'

# Restaurar as mesmas cópias aos caminhos originais, conferindo os hashes.
.\scripts\organize-runtime.ps1 -RuntimeRoot C:\SextaFeiraRuntime -Action Undo -PlanFile 'CAMINHO_PRIVADO_DO_PLANO'
```

O plano permite reaplicar depois de `Undo`. Repetir uma ação já satisfeita não move novamente os arquivos. A operação confere todos os itens antes do primeiro movimento e reverte os movimentos concluídos se houver uma exceção. O estado final do plano é gravado por substituição atômica. Não utiliza exclusão, recursão ou sobrescrita de destino.

As movimentações preservam os bytes e os instaladores. Não constituem limpeza que libere espaço: a mudança é de localização no mesmo volume. Pacotes recentes e a distribuição Android ativa em `data/android-release` ficam fora da lista de movimentos.

## Escopo e serviços existentes

A organização não move projetos Team Bike, diretórios Windows, bancos de dados, modelos, credenciais ou configurações em uso. O inventário lista nomes de diretórios na raiz, os serviços relevantes e os listeners conhecidos; não copia conteúdo de arquivos, linhas de comando ou credenciais. Serviços, portas e projetos de produção precisam de revisão própria antes de qualquer futura reorganização.

Para verificar a aplicação, utilize `scripts/health.ps1 -RuntimeRoot ...`, que usa a credencial apenas em memória. Para serviço, consulte `scripts/service.ps1 -Action Status -RuntimeRoot ...`. Atualizações e restauração de bancos continuam seguindo os procedimentos específicos: nunca restaure uma cópia antiga sobre conversas novas sem avaliação.

## Verificação realizada em 13/11/2026

Foram arquivadas dez cópias antigas, totalizando **1.658.131 bytes**. O ciclo `Apply → Undo → Apply` foi executado no servidor; os dez SHA-256 e as localizações corretas foram conferidos em cada fase. A versão com gravação atômica do estado também passou por reversão e reaplicação. A repetição de `Apply` não realizou novos movimentos.

Planos de teste com nome fora da lista e SHA-256 alterado foram rejeitados antes de mover qualquer arquivo. O inventário e o índice operacional ficaram privados no runtime. A verificação dos serviços e listeners de produção é registrada em recibo privado; nenhum serviço é reiniciado pelo organizador.

O resultado é uma organização delimitada dos artefatos próprios e um mapa do servidor. Não declara que todos os diretórios, arquivos pessoais ou projetos de produção da máquina foram reorganizados.
