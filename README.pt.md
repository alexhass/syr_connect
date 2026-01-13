![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)

# SYR Connect - Integração Home Assistant

![Syr](custom_components/syr_connect/logo.png)

Esta integração personalizada permite controlar dispositivos SYR Connect através do Home Assistant.

## Instalação

### HACS (recomendado)

1. Abra o HACS no Home Assistant
2. Vá para "Integrations"
3. Clique nos três pontos no canto superior direito
4. Selecione "Custom repositories"
5. Adicione a URL do repositório
6. Selecione a categoria "Integration"
7. Clique em "Add"
8. Procure por "SYR Connect" e instale
9. Reinicie o Home Assistant

### Instalação manual

1. Copie a pasta `syr_connect` para seu diretório `custom_components`
2. Reinicie o Home Assistant

## Configuração

1. Vá em Configurações > Dispositivos e Serviços
2. Clique em "+ Adicionar integração"
3. Procure por "SYR Connect"
4. Insira suas credenciais do aplicativo SYR Connect:
   - Nome de usuário
   - Senha

## Funcionalidades

A integração cria automaticamente entidades para todos os seus dispositivos SYR Connect.

### Dispositivos suportados

Funciona com amaciadores SYR que aparecem no portal SYR Connect.

Testado e relatado funcionando:
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

Não testado, mas deve funcionar:
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect
- SYR LEX 1500 Connect Individual
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Alternante
- SYR LEX 1500 Connect Triplo
- SYR IT 3000 Sistema pendular
- Outros modelos SYR com capacidade Connect ou gateway retrofit

**Nota**: Se o dispositivo estiver visível na sua conta SYR Connect, a integração o descobrirá automaticamente. Para dispositivos não testados, compartilhar dados de diagnóstico ajuda a expandir o suporte.

### Funcionalidade suportada

#### Sensores
- Monitoramento dureza da água entrada/saída
- Capacidade restante
- Capacidade total
- Unidade de dureza
- Estado de regeneração (ativo/inativo)
- Número de regenerações
- Intervalo e horário de regeneração
- Gestão de sal (volume, estoque)
- Monitoramento de pressão e fluxo
- Estado operacional e alarmes

#### Sensores binários
- Regeneração ativa
- Estado operacional
- Alarmes

#### Botões (Ações)
- Regenerar agora (`setSIR`)
- Regeneração múltipla (`setSMR`)
- Reiniciar dispositivo (`setRST`)

### Limitações conhecidas

- Dependência da nuvem: requer conexão à Internet e serviço SYR Connect
- Intervalo mínimo recomendado: 60 segundos
- Principalmente leitura: apenas ações de regeneração disponíveis
- Uma conta SYR Connect por instância Home Assistant
- Sem API local: comunicação via cloud

## Como os dados são atualizados

A integração consulta a API SYR Connect em intervalos regulares (padrão 60s):

1. Login
2. Descoberta de dispositivos
3. Recuperação de status
4. Atualização das entidades no Home Assistant

Se um dispositivo estiver offline, as entidades ficarão `unavailable` até a próxima atualização bem-sucedida.

## Exemplos de uso
- Automações: alerta baixo de sal, relatório diário de regeneração, notificação de alarme, monitoramento de fluxo, regeneração agendada (veja o README original para exemplos)

## Opções de configuração

O intervalo de varredura pode ser ajustado nas opções da integração (padrão 60s).

## Remoção

1. Configurações > Dispositivos e Serviços
2. Selecione SYR Connect
3. Menu (⋮) > Excluir

## Solução de problemas

- É possível baixar dados de diagnóstico (dados sensíveis são mascarados)
- Erros de conexão/autenticação: verifique credenciais, teste o app, confira os logs

## Dependências

- `pycryptodomex==3.19.0`

## Licença

Licença MIT - veja o arquivo LICENSE

## Agradecimentos

- Baseado no adaptador [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) de TA2k.
- Obrigado à equipe SYR IoT pelos logos.
