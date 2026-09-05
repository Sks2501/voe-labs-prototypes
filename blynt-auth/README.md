# Blynt Beta App — Remote Authorization

O aplicativo consulta `auth.json` na inicialização e periodicamente enquanto está aberto.

- `"enabled": true` — permite iniciar e usar o aplicativo.
- `"enabled": false` — bloqueia o aplicativo e exibe a mensagem definida em `message`.
- `minimumVersion` — versão mínima permitida do cliente.
- `message` — mensagem exibida quando o acesso estiver desativado.

A validação é feita no processo principal do Electron. O cliente opera em modo fail-closed na inicialização: se não conseguir validar uma resposta válida do GitHub após as tentativas configuradas, não carrega a interface principal.
