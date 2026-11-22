<!-- markdownlint-disable-next-line MD041 -->
<img src="custom_components/syr_connect/brand/logo.png" alt="Syr" width="200">

# SYR Connect - Integração para o Home Assistant

[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![syr_connect installs](https://img.shields.io/badge/dynamic/json?logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.syr_connect.total)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)
[![Quality scale: Platinum](https://img.shields.io/badge/Quality%20scale-Platinum%20%F0%9F%8F%86-b5d2e0?style=flat)](https://github.com/alexhass/syr_connect/blob/main/quality_scale.yaml)

<!-- ha-marketplace:exclude-start -->

[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

<!-- ha-marketplace:exclude-end -->

Esta integração personalizada permite controlar os dispositivos SYR Connect através do Home Assistant. Também pode ser utilizada com dispositivos idênticos de outras marcas. As instalações mistas de marcas diferentes também são suportadas.

| Marca | Ligação |
| ------ | ------ |
| comfort by sanibel | <https://comfort-by-sanibel.de/> |
| CONEL | <https://www.conel.de/> |
| DITECH | <https://www.ditech-haustechnik.de/> |
| Hansgrohe Pontos | <https://www.hansgrohe.de/> |
| mein concept | <https://www.mein-concept.de/> |
| mein Optima | <https://www.mein-optima.de/> |
| POLYGONVATRO | <https://www.polygongroup.com/de-DE/> |
| Reliance Valves | <https://www.rwc.com/brands/reliance-valves> |
| SYR | <https://www.syr.de/> |
| SYR Oceanic | <https://www.debestewaterbehandeling.be/> |
| TAKE | <https://take-bad.de/> |

## Capturas de ecrã

Exemplos de interfaces dos dispositivos:

![Captura de ecrã do LEXplus10S](docs/assets/screenshots/en/lexplus10s.png)

![Captura de ecrã do Safe-T+](docs/assets/screenshots/en/safetplus.png)

<!-- ha-marketplace:exclude-start -->

## Instalação

[![Abrir a instância do Home Assistant e abrir um repositório no Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=alexhass&repository=syr_connect&category=integration)

### Marketplace (recomendado)

1. Ir a Definições > Marketplace.
2. Procurar "SYR Connect".
3. Clicar em "Instalar".
4. Reiniciar o Home Assistant.

### Instalação manual

1. Copiar a pasta `syr_connect` para o diretório `custom_components`.
2. Reiniciar o Home Assistant.

<!-- ha-marketplace:exclude-end -->

## Configuração

[![Abrir a instância do Home Assistant e iniciar a configuração de uma nova integração.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)

A integração suporta dois modos de configuração:

### Configuração com a API na nuvem (todos os dispositivos)

1. Ir a Definições > Dispositivos e Serviços.
2. Clicar em "+ Adicionar Integração".
3. Procurar "SYR Connect".
4. Selecionar "Nuvem".
5. Introduzir as credenciais da aplicação móvel:
   - **Serviço**: A aplicação em que os dispositivos estão configurados
   - **Nome de utilizador**: Nome de utilizador da conta nesta aplicação
   - **Palavra-passe**: Palavra-passe da conta nesta aplicação

### Configuração com a API local (apenas dispositivos mais recentes)

Para dispositivos mais recentes com uma API JSON local, por exemplo os dispositivos NeoSoft e Trio, SafeTech Lock, TRIO Lock, AC 3200 e RSA Connect, bem como os seus dispositivos idênticos de outras marcas. A seleção do modelo durante a configuração apresenta todos os modelos suportados:

1. Ir a Definições > Dispositivos e Serviços.
2. Clicar em "+ Adicionar Integração".
3. Procurar "SYR Connect".
4. Selecionar "Local".
5. Introduzir os dados do dispositivo:
   - **Modelo do dispositivo**: Modelo do dispositivo (p. ex., NeoSoft 2500 Connect)
   - **Nome do anfitrião ou endereço IP**: Endereço IP ou nome do anfitrião do dispositivo (p. ex., `192.168.178.199`)

**Nota**: O endereço IP do dispositivo aparece na lista de clientes DHCP do router ou no menu do ecrã do dispositivo.

**Importante**: Para um funcionamento estável, o dispositivo deve ter um **endereço IP estático** ou uma **concessão DHCP reservada** (reserva DHCP). Se o endereço IP do dispositivo mudar, a integração perde a ligação. O novo endereço é introduzido com "Reconfigurar" no menu de três pontos (⋮) da entrada. A entrada fica associada ao seu dispositivo pelo número de série: outro dispositivo no novo endereço é rejeitado e tem de ser adicionado como uma nova entrada. Em alternativa, pode ser utilizado um nome de anfitrião se a rede suportar a resolução DNS local.

## Funcionalidades

A integração cria automaticamente entidades para todos os dispositivos SYR Connect da conta.

### Dispositivos suportados

Esta integração funciona com os amaciadores de água e os dispositivos de deteção de fugas da SYR e com outros dispositivos que aparecem na nuvem SYR Connect (através da respetiva aplicação móvel).

Testados e comunicados como funcionais:

- CONEL CLEAR PRO FILL
- CONEL CLEAR PRO Floor Sensor
- CONEL CLEAR PRO LEAKAGE PROTECTION
- CONEL CLEAR PRO SOFT
- concept SafeFloor Floor Sensor
- DITECH Wireless Floor Sensor
- Optima T2 Floor Sensor
- POLYGONVATRO Wireless Floor Sensor
- Sanibel Leak Protection Module A25
- Sanibel Softwater UNO A25
- Sanibel Wireless Floor Sensor A25
- SYR All-in-One+
- SYR LEX 1500 Connect Single (LEX10/LEX20/LEX30/LEX40/LEX60/LEX80/LEX100)
- SYR LEX Plus 10 Connect
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect
- SYR NeoSoft 2500 Connect
- SYR SafeFloor Connect
- SYR Safe-T+ Connect
- SYR SafeTech Connect
- SYR SafeTech plus Connect
- SYR SafeTech V3 Connect
- SYR SafeTech V4 Connect
- SYR TRIO DFR/LS Connect 2425
- SYR TRIO Lock Connect
- SYR Oceanic i-LEX / Limex iQ Single (L10/L12/L15/L20/L25/L30/L40/L50/L60/L70/L80/L90/L100)

Outros dispositivos também são de interesse, mas podem ter de ser integrados ou pelo menos testados (agradecem-se os relatos):

- CONEL CLEAR PRO MULTICONTROL-KIT
- CONEL CLEAR PRO SOFT TWIN
- concept 200 Dual Water Softener
- concept 200 Replacement Filter
- concept 300 Automatic Backwash RSA
- concept 300 Trio Filter with Leak Protection
- concept Dual Water Softener
- concept Single Water Softener
- DITECH Automatic Backwash HWS/RF
- DITECH Backwash Filter Protect
- DITECH Connection Module Plus
- DITECH Dual Water Softener
- DITECH Hygiene Flush Box
- DITECH Single Water Softener
- Hansgrohe PontosBase
- Optima Dual Water Softener
- Optima Single Water Softener
- Optima T Replacement Filter
- Optima T2 Dual Water Softener
- POLYGONVATRO SafeTech Connect (vendido com o seguro de habitação da AXA como "Wasserwächter")
- RWC MultiSafe Floor Leak Sensor
- RWC MultiSafe Leak Detector Control Valve
- Sanibel Automatic Backwash System RSA A25
- Sanibel Softwater DUO A25
- SYR AC 3200 Connect
- SYR AC All-in-One 3228 Connect
- SYR CONTROLICmini
- SYR HVA
- SYR HygBox Connect
- SYR Hygiene Module (fria / quente / fria e quente)
- SYR Inliner-HWA 3300
- SYR IT 3000 Pendulum system
- SYR LEX 1500 Connect Alternating
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Triple
- SYR NeoDos Connect
- SYR NeoSoft 5000 Connect
- SYR NeoSoft Lock Connect I / II
- SYR RSA Connect
- SYR Safe-T Communication Module
- SYR Safe-T Hygiene Module
- SYR Safe-T Master / Slave
- SYR SafeTech Lock Connect
- SYR Trio LS Connect
- TAKE Dual Water Softener
- TAKE Single Water Softener

**Nota**: Se um dispositivo estiver visível na conta SYR Connect, a integração deteta-o e cria as entidades automaticamente. Para um "dispositivo não testado", a partilha dos diagnósticos ajuda a encontrar valores desconhecidos e a verificar se tudo funciona como previsto. Assim, a lista de dispositivos testados também pode ser alargada.

### Dispositivos não suportados

- Dispositivos SYR Oceanic Limex SMART COMPACT/MINI/MAXI. Estes dispositivos utilizam outro portal na nuvem (`i-lexconnect.com`) em vez do serviço na nuvem SYR Connect. São dispositivos Husty SaoCal com outra marca.
- Dispositivos Husty SaoCal. Ver [husty_integration_home_assistant](https://github.com/trafopowielacz/husty_integration_home_assistant).

### Funcionalidades suportadas

#### Sensores

A integração oferece uma monitorização completa dos dispositivos:

#### Qualidade da água e capacidade

- Monitorização da dureza da água bruta e amaciada
- Condutividade da água (µS/cm)
- Gama de dureza da água (macia, média, dura), estimada a partir da condutividade (família SafeTech)
- Fator de condutividade
- Temperatura da água (°C)
- Acompanhamento da capacidade de amaciamento restante
- Capacidade da resina por depósito (até 3 depósitos, %)
- Monitorização do volume total
- Apresentação da unidade de dureza da água

#### Informações sobre a regeneração

- Estado da regeneração e indicador do depósito ativo (até 3 depósitos)
- Modo de regeneração (Padrão / ECO / Power / Automático)
- Número de regenerações efetuadas
- Data e hora da última regeneração
- Definições do intervalo de regeneração
- Horário de regeneração
- Contadores de ciclos e tempos

#### Gestão do sal

- Quantidade de sal nos reservatórios (1–3)
- Reserva de sal (semanas restantes)
- Capacidade de reserva da resina por garrafa

#### Monitorização do sistema

- Monitorização da pressão da água
- Caudal (atual e instantâneo)
- Contador de caudal (consumo total)
- Tensão da bateria e da rede elétrica
- Estado de alarmes, notificações e avisos (código atual e as últimas 8 entradas do histórico)

#### Proteção contra fugas (LEXplus10SL / Trio DFR/LS)

- Limites de volume e de duração da proteção contra fugas (perfis de presença e de ausência)
- Índice do perfil de proteção contra fugas ativo
- Perfis de proteção contra fugas 1–8 (limite de volume, duração máxima, limiar de caudal, indicadores de aviso e de alarme sonoro)
- Temporizador de desativação temporária
- Limiar de aviso de fuga (%)

#### Teste de microfuga (Trio DFR/LS, SafeTech, SafeTech+, TRIO Lock, SafeTech Lock)

- Intervalo e estado do teste de microfuga
- Duração do teste e número de eventos

#### Fase de autoaprendizagem (Trio DFR/LS, SafeTech+, TRIO Lock, SafeTech Lock)

- Tempo de autoaprendizagem restante e decorrido
- Caudal e volume acumulado durante a autoaprendizagem
- Definições da autoaprendizagem: margem de volume e de tempo, margem de caudal, caudal mínimo

#### Sensor de pavimento (SafeFloor)

- Humidade e temperatura atuais
- Nível da bateria (%)
- Estado do alarme

#### Filtro e retrolavagem

- Tipo de filtro (SafeTech, SafeTech Lock, TRIO Lock, AC All-in-One 3228 Connect)
- Teor de ferro (família LEX)
- Contadores de retrolavagens automáticas e manuais (retrolavagem automática RSA)

#### Manutenção

- Próximas datas de manutenção agendadas (semestral e anual)
- Consumo diário de água previsto

#### Informações do dispositivo

- Número de série
- Versão do firmware e modelo
- Tipo de dispositivo e fabricante
- Informações de rede (IP, MAC, gateway)
- Estado da ligação Wi-Fi e intensidade do sinal
- Fuso horário (desvio UTC)

#### Sensores binários

- **Alarme sonoro**: Indica se o alarme sonoro toca em caso de alarme.
- **Proteção contra fugas**: Indica se a proteção contra fugas está ativa ou desativada.
- **Teste da válvula**: Indica se está a decorrer um teste da válvula.
- **Verificação de firmware**: Indica se está disponível um firmware novo (verificado no arranque e a cada 6 horas).
- **Hora de verão**: Indica se o dispositivo muda automaticamente para a hora de verão.
- **Sensor de temperatura**, **Sensor de pressão**, **Sensor de condutividade**: Indicam se o sensor de medição está ativo ou desativado.
- **Monitorização do sensor de pavimento**: Indica se a monitorização dos sensores de pavimento está ativada.

#### Botões (ações)

- **Regenerar agora**: Iniciar uma regeneração imediata.
- **Repor alarme**: Apagar as mensagens de alarme ativas.
- **Repor notificação**: Apagar as mensagens de notificação.
- **Repor aviso**: Apagar as mensagens de aviso.
- **Iniciar teste de microfuga**: Iniciar o teste de microfuga. A válvula permanece fechada durante cerca de 4 minutos, e retirar água durante o teste dá um resultado negativo (apenas API local).
- **Purga manual (água fria)**, **Purga manual (água quente)**: Iniciar uma purga manual da canalização de água (módulo de higiene).

#### Interruptores

- **Alarme sonoro**: Ativar ou desativar o alarme sonoro em caso de alarme.
- **Permitir mudança de perfil no dispositivo**: Permitir ou bloquear a mudança do perfil de proteção contra fugas com o botão do dispositivo.
- **Modo de enchimento**: Ativar ou desativar o enchimento automático (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect e os seus dispositivos idênticos de outras marcas, All-in-One+).
- **Enchimento inicial**: Iniciar ou parar o enchimento inicial (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect e os seus dispositivos idênticos de outras marcas, All-in-One+).
- **Enchimento manual**: Iniciar ou parar o enchimento manual (All-in-One+).
- **Retrolavagem automática**: Ativar ou desativar a retrolavagem automática (retrolavagem automática RSA).
- **Lembrete de retrolavagem**: Ativar ou desativar o lembrete de retrolavagem (retrolavagem automática RSA).
- **Purga por estagnação**, **Purga por temperatura**, **Purga periódica**: Ativar ou desativar as três funções de purga (HygBox).

#### Seletores (configuração)

- **Hora de regeneração**: Definir a hora diária da regeneração (intervalos de 15 minutos).
- **Perfil de proteção contra fugas ativo**: Selecionar o perfil de proteção contra fugas ativo (em dispositivos com vários perfis).
- **Quantidade de sal no reservatório 1–3**: Definir a quantidade de sal por reservatório (conforme o modelo, até 3 reservatórios).
- **Intervalo de regeneração**: Definir a frequência da regeneração (conforme o modelo: até 3, 4 ou 99 dias).
- **Orientação do ecrã**: Definir a orientação do ecrã (0 / 90 / 180 / 270 graus, em dispositivos com ecrã).
- **Idioma do dispositivo**: Definir o idioma do ecrã do dispositivo: alemão, inglês, espanhol, italiano ou polaco (SafeTech).
- **Modo de regeneração**: Selecionar Padrão / ECO / Power / Automático (nos dispositivos que o suportam).
- **Dureza da água bruta**, **Dureza da água amaciada**: Definir a dureza da água bruta e da água amaciada (família LEX, CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect e os seus dispositivos idênticos de outras marcas, All-in-One+). A unidade segue a unidade de dureza configurada no dispositivo (°dH, °fH, °e, mg/l CaCO₃, ppm, mmol/l ou mval/l).
- **Tratamento da água e enchimento** (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect e os seus dispositivos idênticos de outras marcas, All-in-One+): Tamanho e tipo do cartucho, dureza da água amaciada ou condutividade máxima à saída (conforme o cartucho), período de enchimento, número de ciclos de enchimento, duração e quantidade máximas de enchimento, pressão alvo, limiar de aviso da capacidade restante, volume e duração máximos do enchimento inicial.
- **Sensor de pavimento** (SafeFloor): Duração do alarme, limiares mínimo e máximo de humidade e temperatura ("Desligado" desativa um limiar), intervalo de medição e intervalo de sincronização das definições.
- **Purga de higiene** (HygBox): Tipo de água, tempo de estagnação e volume de purga, temperatura de início e de paragem, duração máxima da purga e purgas por dia, intervalo e volume da purga periódica, intervalo de sincronização das definições.
- **Purga de higiene** (módulo de higiene, Safe-T Hygiene Module): Tempo de estagnação, intervalo de purga, limite de temperatura, duração máxima e volume máximo de purga da canalização de água fria e da de água quente.
- **Doseamento** (NeoDos Connect): Tamanho do bidão, líquido de doseamento e modo de funcionamento.
- **Retrolavagem** (retrolavagem automática RSA): Intervalo de retrolavagem e intervalo de lembrete de retrolavagem (1–365 dias).
- **Proteção contra fugas** (Safe-T+): Nível de proteção contra fugas em presença e em ausência (um nível em ausência ativa o perfil de ausência, «Desligado» volta ao perfil de presença), tempo de fuga e desativação temporária da proteção contra fugas.

#### Controlo da válvula

- **Fecho da válvula**: Controlar a válvula principal de corte de água.
  - Abrir e fechar a válvula.
  - Monitorizar a posição e o estado atuais da válvula.
  - Integração com automatizações de deteção de fugas para o corte automático.

#### Atualização de firmware

- **Atualização de firmware**: Indica se está disponível um firmware novo e instala-o. O dispositivo tem de estar ligado à Internet. O dispositivo não comunica o número da nova versão.

### Modos de API

A integração suporta dois modos de API:

#### API na nuvem (baseada em XML)

- **Suportada por**: Todos os dispositivos SYR Connect
- **Ligação**: Através do serviço na nuvem SYR Connect
- **Autenticação**: Nome de utilizador e palavra-passe da conta SYR Connect
- **Vantagens**: Funciona com todos os modelos de dispositivo, acesso remoto a partir de qualquer lugar
- **Requisitos**: Ligação à Internet, conta SYR Connect

#### API local (baseada em JSON)

- **Suportada por**: Modelos mais recentes com uma API local integrada, por exemplo NeoSoft, Trio DFR/LS, TRIO Lock, SafeTech Lock, AC 3200, RSA, Pontos Base, All-in-One+, HygBox e variantes mais recentes do SafeTech, também de outras marcas. A seleção do modelo durante a configuração apresenta todos os modelos suportados.
- **Ligação**: Diretamente ao dispositivo através da rede local (porta 5333).
- **Autenticação**: Não são necessárias credenciais.
- **Vantagens**: Sem dependência da Internet, tempos de resposta mais rápidos, sem limites de pedidos da nuvem.
- **Requisitos**: O dispositivo tem de estar na mesma rede que o Home Assistant e precisa de um endereço IP estático ou de um nome de anfitrião.

O modo de API é escolhido durante a configuração (Nuvem ou Local).

## Como os dados são atualizados

A integração consulta a API do dispositivo a intervalos regulares (predefinição: 60 segundos). O processo de atualização depende do modo de API:

### Processo de atualização com a API na nuvem

1. **Início de sessão**: Autentica-se na API na nuvem SYR Connect com as credenciais.
2. **Deteção de dispositivos**: Obtém todos os projetos e dispositivos associados à conta, no arranque e depois a cada 30 minutos. Um dispositivo eliminado da conta é removido do Home Assistant juntamente com as suas entidades.
3. **Atualizações de estado**: Para cada dispositivo, obtém o estado atual com todos os valores dos sensores.
4. **Atualizações de entidades**: Atualiza todas as entidades do Home Assistant com os valores mais recentes.

### Processo de atualização com a API local

1. **Atualizações de estado**: Obtém o estado do dispositivo diretamente do ponto de acesso local.
2. **Atualizações de entidades**: Atualiza todas as entidades do Home Assistant com os valores mais recentes.

A API local é mais rápida e não depende da ligação à Internet, o que a torna mais fiável para a monitorização em tempo real e para as automatizações.

Se uma atualização falhar temporariamente (p. ex., tempo limite esgotado, manutenção da nuvem ou uma resposta incompleta), as entidades mantêm os últimos valores e o erro é escrito no registo. As entidades só ficam indisponíveis quando a nuvem comunica que o dispositivo está offline. Permanecem indisponíveis até o dispositivo voltar a enviar um estado completo.

Enquanto não for possível obter quaisquer dados, a integração consulta com menos frequência: o intervalo duplica após cada atualização falhada, até 15 minutos. A primeira atualização bem-sucedida repõe o intervalo configurado.

Se não for possível obter dados durante mais de 1 hora, a falha deixa de ser considerada temporária: as entidades afetadas ficam indisponíveis e é apresentada uma mensagem em **Definições** → **Reparações**. Ambas desaparecem assim que voltarem a ser obtidos dados.

### Histórico de medições do SafeFloor

Um SafeFloor mede regularmente a temperatura e a humidade, mas só envia as medições para a nuvem a cada poucos dias, pelo que os seus sensores mostram uma linha plana seguida de um salto. A integração obtém as medições individuais da nuvem a cada 12 horas e guarda-as como estatísticas com o nome dos sensores (p. ex., "Lavandaria Temperatura"). Para ver a curva real, é adicionado um cartão a um painel:

1. Abrir o painel e selecionar **Editar painel** no canto superior direito.
2. Selecionar **Adicionar cartão**, escrever `Statistics` em **Pesquisar cartões** e escolher **Gráfico de estatísticas**.
3. Selecionar **Mostrar editor de código**, substituir o texto por um dos excertos abaixo e selecionar **Guardar**.
4. Selecionar **Concluído**.

`123456789` é substituído pelo número de série do SafeFloor. É necessário um cartão por medição.

Temperatura:

```yaml
type: statistics-graph
title: Temperatura
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_getcel_history
```

Humidade:

```yaml
type: statistics-graph
title: Humidade
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_gethmd_history
```

A nuvem só guarda as medições dos últimos 6 dias. O intervalo de sincronização do sensor deve manter-se em 6 dias ou menos; caso contrário, perdem-se medições. As estatísticas são eliminadas juntamente com o dispositivo.

### Limitações conhecidas

- **Dependência da nuvem**: A API na nuvem requer uma ligação à Internet ativa e um serviço na nuvem operacional.
- **Intervalo de atualização**: A API na nuvem permite um intervalo de atualização de pelo menos 60 segundos, a API local de pelo menos 10 segundos.
- **Acesso de escrita limitado**: São suportadas alterações de configuração (hora de regeneração, quantidades de sal, intervalos) e ações de controlo (regeneração, controlo da válvula), mas algumas definições avançadas podem estar disponíveis apenas na aplicação SYR Connect.
- **Suporte da API local**: Nem todos os modelos disponibilizam uma API JSON local. LEX 1500, LEXplus, i-LEX, Safe-T, SafeFloor, HVA, os módulos de higiene e as variantes mais antigas do SafeTech requerem o acesso através da API na nuvem.

## Casos de utilização e exemplos

### Exemplos de automatizações

Os exemplos utilizam a sintaxe YAML de `configuration.yaml`. Em todos os exemplos, `<serial_number>` é substituído pelo número de série do dispositivo e `<device_name>` pelo nome do dispositivo da aplicação móvel no Home Assistant.

#### Alerta de sal baixo

Notificação quando a reserva de sal está a esgotar-se:

```yaml
automation:
  - alias: "SYR: Alerta de sal baixo"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Restam menos de 2 semanas de sal
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Amaciador de água"
          message: "Reserva de sal baixa - restam menos de 2 semanas"
```

#### Relatório diário de regeneração

Resumo diário das regenerações, da capacidade restante e da reserva de sal:

```yaml
automation:
  - alias: "SYR: Relatório diário de regeneração"
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Relatório diário do amaciador de água"
          message: >
            Regenerações (total): {{ states('sensor.syr_connect_<serial_number>_getnor') }}
            Capacidade restante: {{ states('sensor.syr_connect_<serial_number>_getres') }} L
            Reserva de sal: {{ states('sensor.syr_connect_<serial_number>_getss1') }} semanas
```

#### Notificação de alarme

Notificação imediata quando o dispositivo comunica um alarme:

```yaml
automation:
  - alias: "SYR: Notificação de alarme"
    triggers:
      - trigger: template
        value_template: >
          {{ states('sensor.syr_connect_<serial_number>_getala')
             not in ['no_alarm', 'unknown', 'unavailable'] }}
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "⚠️ Alarme SYR"
          message: "Alarme atual: {{ states('sensor.syr_connect_<serial_number>_getala') }}"
          data:
            priority: high
```

#### Monitorização do caudal de água

Alerta em caso de caudal de água invulgarmente elevado durante vários minutos (possível fuga):

```yaml
automation:
  - alias: "SYR: Alerta de caudal elevado"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 1200  # Caudal superior a 1200 l/h (20 l/min)
        for:
          minutes: 5
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Caudal de água elevado detetado"
          message: "Caudal de água invulgar - possível fuga"
```

#### Sensor de fugas: fechar a válvula de água

Fecha a válvula de corte de água SYR com a ação padrão `valve.close` quando um sensor de fugas deteta água. Os ID das entidades são substituídos pelos utilizados na instalação. Esta automatização pode tornar-se uma ação de segurança crítica, pelo que tem de ser testada com muito cuidado.

```yaml
automation:
  - alias: "SYR: Fechar a válvula em caso de fuga"
    triggers:
      - trigger: state
        entity_id: binary_sensor.house_leak_sensor
        to: "on"
    actions:
      - action: valve.close
        target:
          entity_id: valve.syr_connect_<serial_number>_getab
      - action: notify.mobile_app_<device_name>
        data:
          title: "SYR: Fuga detetada - válvula fechada"
          message: "Foi detetada uma fuga de água - a válvula de corte de água SYR foi fechada automaticamente."
```

#### Regeneração ao fim de semana

Inicia uma regeneração aos sábados e domingos às 03:00:

```yaml
automation:
  - alias: "SYR: Regeneração ao fim de semana"
    triggers:
      - trigger: time
        at: "03:00:00"
    conditions:
      - condition: time
        weekday:
          - sat
          - sun
    actions:
      - action: button.press
        target:
          entity_id: button.syr_connect_<serial_number>_setsir
```

## Opções de configuração

### Intervalo de atualização

Por predefinição, os dados são atualizados a cada 60 segundos. O intervalo é definido nas opções da integração: pelo menos 60 segundos para a nuvem, pelo menos 10 segundos para os dispositivos locais e no máximo 600 segundos em ambos os casos.

1. Abrir Definições > Dispositivos e Serviços.
2. Abrir a integração SYR Connect.
3. Selecionar "Configurar".
4. Ajustar o intervalo de atualização (em segundos).

## Remoção

Para remover a integração do Home Assistant:

1. Ir a Definições > Dispositivos e Serviços.
2. Procurar a integração SYR Connect.
3. Clicar no menu de três pontos (⋮).
4. Selecionar "Eliminar".
5. Confirmar a eliminação.

Todos os dispositivos e entidades associados são removidos automaticamente.

## Resolução de problemas

### Transferir os diagnósticos

Em caso de problemas, os diagnósticos da entrada da integração ajudam. Contêm os dados de todos os dispositivos da entrada:

1. Abrir Definições > Dispositivos e Serviços.
2. Abrir a integração SYR Connect.
3. Abrir o menu de três pontos (⋮) da entrada (conta ou dispositivo local).
4. Selecionar "Transferir diagnósticos".

As palavras-passe, os nomes de utilizador, os dados de sessão, o número de código do dispositivo, os endereços IP, os gateways e o nome da rede Wi-Fi são removidos do ficheiro, e o número de série é ocultado.

### Registos de depuração

A ativação e a desativação do registo de depuração estão descritas em [docs/howto-debugging.md](docs/howto-debugging.md) (em inglês).

### A ligação falha

- **Verificar as credenciais**: Confirmar o nome de utilizador e a palavra-passe da aplicação SYR Connect.
- **Testar a aplicação**: O início de sessão na aplicação móvel SYR Connect tem de funcionar com a mesma conta.
- **Consultar os registos**: Ir a Definições > Sistema > Registos e procurar erros de "syr_connect".
- **Problemas de rede**: O Home Assistant tem de ter acesso à Internet.

### Erros de autenticação

Em caso de erros "Authentication failed":

1. Verificar as credenciais.
2. A integração pede uma nova autenticação.
3. Ir a Definições > Dispositivos e Serviços.
4. Clicar em "Autenticar" na integração SYR Connect.
5. Introduzir novamente as credenciais.

A nova autenticação e "Reconfigurar" só alteram a palavra-passe da conta. Outro nome de utilizador é outra conta: é aí rejeitado e tem de ser adicionado como uma nova entrada.

### Nenhum dispositivo encontrado

- **Configuração da aplicação**: Os dispositivos têm de estar corretamente configurados na aplicação SYR Connect.
- **Acesso à conta**: A conta tem de ser aquela em que os dispositivos estão configurados.
- **Estado dos dispositivos**: Verificar se os dispositivos estão online na aplicação SYR Connect.
- **Registos**: Consultar os registos do Home Assistant para encontrar mensagens de erro específicas.

### As entidades aparecem como indisponíveis

- **Dispositivo offline**: A nuvem comunica que o dispositivo está offline. A alimentação elétrica e a ligação de rede do dispositivo têm de ser verificadas.
- **Aplicação SYR Connect**: O dispositivo tem de aparecer como online na aplicação SYR Connect.
- **Novamente online**: As entidades voltam a ficar disponíveis assim que o dispositivo envia um estado completo.

- **Sem ligação há mais de 1 hora**: Não foi possível obter dados da nuvem ou do dispositivo durante mais de 1 hora. É apresentada uma mensagem em **Definições** → **Reparações**. A ligação à Internet e o estado da nuvem SYR Connect têm de ser verificados.
- **Problema de rede**: Se não foi possível resolver o nome do anfitrião ou abrir qualquer ligação, a mensagem indica a rede como causa. A ligação de rede e as definições de DNS do Home Assistant têm de ser verificadas e, num dispositivo local, também o seu endereço IP.

Os problemas temporários com a ligação ou com o serviço na nuvem não tornam as entidades indisponíveis. As entidades mantêm os últimos valores e o erro é escrito no registo.

### Utilização elevada de CPU ou memória

- **Aumentar o intervalo de atualização**: Definir um valor mais alto (p. ex., 120–300 segundos) nas opções da integração.
- Isto reduz as chamadas à API e a carga do sistema.

<!-- ha-marketplace:exclude-start -->

## Dependências

A integração requer os seguintes pacotes Python:

- `pycryptodomex>=3.19.0,<4.0`: Para a encriptação e desencriptação AES
- `defusedxml>=0.7.1,<1.0`: Para a análise segura de XML (impede ataques XXE)

**Nota**: A integração utiliza `defusedxml` para a análise segura de XML e `pycryptodomex` (e não `pycryptodome`) para evitar conflitos com as bibliotecas criptográficas integradas no Home Assistant.

O Home Assistant instala os pacotes **automaticamente** quando:

1. A integração é adicionada através da interface de utilizador.
2. O Home Assistant é reiniciado após a instalação.

Os requisitos de sistema detalhados e a resolução de problemas encontram-se em [REQUIREMENTS.md](REQUIREMENTS.md) (em inglês).

<!-- ha-marketplace:exclude-end -->

## Exclusão de responsabilidade

### IMPORTANTE: Ler antes de utilizar a integração

Esta integração controla sistemas de tratamento de água e de corte de água. Uma configuração incorreta ou automatizações com falhas podem provocar danos causados pela água, falhas do sistema ou danos materiais.

- **Utilização por conta e risco próprios**: Este software é fornecido "tal como está", sem qualquer tipo de garantia.
- **Testes exaustivos**: As automatizações devem ser sempre testadas em condições seguras antes de serem postas em funcionamento.
- **Sistemas críticos**: As automatizações de controlo da válvula podem cortar todo o abastecimento de água e têm de ser testadas com cuidado.
- **Sem responsabilidade**: Os autores e colaboradores não são responsáveis por quaisquer danos, danos causados pela água, danos materiais ou outros problemas resultantes da utilização desta integração.
- **Dependência da nuvem**: Esta integração depende do serviço na nuvem SYR Connect, cuja disponibilidade não é garantida.
- **Plano alternativo**: Tem de existir um acesso alternativo à válvula de corte de água em caso de falha do sistema.

A instalação e a utilização desta integração implicam o reconhecimento destes riscos e a aceitação de a utilizar de forma responsável.

## Licença

Apache License 2.0, ver [LICENSE](LICENSE)

## Agradecimentos

- Inspirado no adaptador [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) de TA2k.
- Muito obrigado à equipa SYR IoT-Development-Team pela partilha dos logótipos.
