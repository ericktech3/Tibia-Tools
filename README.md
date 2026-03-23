# Tibia Tools

App Android não oficial para utilidades de **Tibia**, desenvolvido com **Kivy + KivyMD**.

O foco do projeto é reunir, em um só app, consultas rápidas de personagem, favoritos com monitoramento em segundo plano, calculadoras úteis e integrações com fontes da comunidade.

> Projeto independente, sem afiliação com CipSoft, Tibia.com, TibiaWiki, GuildStats, Tibia Stalker ou ExevoPan.

---

## Visão geral

O app está organizado em 4 abas principais:

- **Home**
- **Char**
- **Share XP**
- **Favoritos**
- **Mais** (atalhos para ferramentas extras)

Além disso, o projeto inclui um **serviço Android em foreground** para monitorar favoritos mesmo com o app fechado.

---

## Funcionalidades

### Home

Tela inicial com atalhos e resumo do que é mais usado:

- **Boosted do dia**
  - boosted creature
  - boosted boss
  - refresh manual
- **Último personagem pesquisado**
  - mostra o último char consultado
  - atalho para abrir no Tibia.com
- **Bosses favoritos com chance High**
  - resumo rápido dos favoritos marcados na tela de bosses

---

### Char

Consulta completa de personagem com foco em informações úteis no dia a dia.

#### Busca de personagem
- pesquisa por nome
- histórico local de buscas recentes
- atalho para abrir o personagem no **Tibia.com**
- botão para **favoritar** o personagem

#### Informações exibidas
Dependendo do retorno das fontes, o app pode mostrar:
- nome e status
- world
- vocation
- level
- residência
- guild
- sex
- achievement points
- married to
- houses
- outros personagens da conta

#### Histórico de XP
- card com **XP dos últimos 30 dias**
- resumo de **7 dias** e **30 dias** quando disponível
- link direto para a fonte externa do histórico
- fallback de parser para evitar falso “Histórico de XP indisponível” em layouts alternativos

#### Mortes recentes
- lista das últimas mortes encontradas
- estimativa de XP perdida por morte
- opção de copiar as mortes

#### Tibia Stalker
- consulta sugestões de personagens relacionados
- exibe resultados por **probabilidade/score**
- link direto para abrir a fonte no navegador

---

### Share XP

Calculadora simples de shared experience:

- recebe o level do personagem
- calcula a faixa permitida para share
- usa a regra clássica:
  - mínimo: `ceil(level * 2/3)`
  - máximo: `floor(level * 3/2)`

---

### Favoritos

Lista de personagens salvos para acompanhamento rápido.

#### Ações da tela
- abrir o personagem
- copiar o nome
- remover dos favoritos
- atualizar status manualmente

#### Monitoramento em segundo plano
O app possui um serviço Android para monitorar favoritos mesmo com o app fechado.

Eventos suportados:
- personagem ficou **online**
- personagem **upou level**
- personagem **morreu**

Comportamento:
- as notificações podem abrir o app direto na aba de personagem
- o serviço roda como **foreground service**, então o Android pode exibir uma notificação fixa do monitor
- há suporte a inicialização automática no boot, quando habilitado nas configurações

---

### Mais

Menu com ferramentas extras do app.

#### Bosses (ExevoPan)
- busca bosses por **world**
- lista chance/indicador retornado pela fonte
- filtro por texto
- ordenação
- favoritos de bosses
- tela separada para **Bosses Favoritos**
- resumo dos favoritos “High” no dashboard
- link para abrir a página do boss no navegador

#### Boosted
- consulta **Boosted Creature** e **Boosted Boss**
- cache local para evitar recargas desnecessárias
- histórico local do que já foi visto
- notificação opcional ao abrir o app quando o boosted mudou

#### Treino (Exercise)
Calculadora para treino com exercise weapons:
- skill: melee, distance, shielding, magic e fist
- vocation
- arma de treino
- skill atual / skill alvo
- percentual restante
- loyalty

Saída:
- quantidade estimada de weapons/charges
- custo aproximado
- resumo do treino

#### Imbuements
Modo offline-first para consulta de imbuements:
- lista local de imbuements
- busca por nome
- filtro por tier
- favoritos de imbuements
- detalhes por tier:
  - Basic
  - Intricate
  - Powerful
- cópia rápida dos detalhes

#### Stamina
Calculadora de regeneração offline:
- stamina atual
- stamina desejada
- cálculo de tempo offline necessário
- horário estimado em que a stamina alvo será atingida

#### Hunt Analyzer
Analisa texto de sessão de hunt e extrai:
- loot
- supplies
- balance
- saída formatada para leitura rápida

#### Novidades
Resumo embutido no app com os recursos adicionados mais recentemente.

#### Sobre
Tela textual com resumo do app e observações sobre fontes.

#### Feedback
Abre o fluxo de feedback do repositório quando a URL do GitHub está configurada nas preferências.

---

## Configurações

A tela de configurações permite ajustar:

### Aparência
- tema claro
- tema escuro

### Notificações ao abrir o app
- avisar quando o **boosted** mudou
- avisar quando algum **boss favorito** está com chance High

### Favoritos em segundo plano
- ativar/desativar monitoramento
- iniciar automaticamente ao ligar o aparelho
- avisar online
- avisar level up
- avisar morte
- definir intervalo do monitor em segundos

### Updates (GitHub)
- configurar a URL do repositório
- checar se existe release nova
- abrir a página de releases
- limpar cache local

---

## Fontes de dados

O app combina fontes oficiais e da comunidade, conforme o tipo de informação:

- **TibiaData**
  - dados gerais de personagem
  - worlds
  - boosted creature / boss
- **Tibia.com**
  - complementos de status e última atividade quando necessário
- **GuildStats**
  - histórico de XP
  - mortes e XP associada
- **Tibia Stalker**
  - sugestões por probabilidade para personagens relacionados
- **ExevoPan**
  - bosses por world
- **GitHub Releases**
  - checagem de atualizações do app

> Como algumas integrações dependem de sites de terceiros, o comportamento pode variar se essas páginas mudarem layout, ficarem fora do ar ou aplicarem proteção temporária.

---

## Stack do projeto

- **Python 3**
- **Kivy**
- **KivyMD 1.2.0**
- **Buildozer**
- **python-for-android**
- **Requests**
- **BeautifulSoup4**

---

## Estrutura do projeto

```text
.
├── main.py                     # composição do app e navegação principal
├── tibia_tools.kv             # arquivo KV raiz
├── assets/                    # ícone e presplash
├── core/                      # regras e cálculos puros
├── features/
│   ├── char/                  # lógica da aba Char
│   ├── favorites/             # lógica da aba Favoritos
│   └── settings/              # lógica das Configurações
├── integrations/              # integrações externas
├── repositories/              # repositórios locais
├── service/                   # serviço Android de monitoramento
├── services/                  # bridge Android, persistência, releases, infraestrutura
├── ui/kv/                     # telas KV modularizadas
├── tests/                     # testes unitários/regressão
├── android/                   # extras Android
├── android_src/               # código Java/Kotlin adicional, se aplicável
├── p4a/                       # hooks do python-for-android
└── buildozer.spec            # configuração de build Android
```

---

## Build local

Exemplo de ambiente Linux/WSL:

```bash
sudo apt update
sudo apt install -y python3 python3-pip git zip unzip openjdk-17-jdk \
  build-essential autoconf automake libtool pkg-config cmake \
  libssl-dev libffi-dev libltdl-dev \
  libncurses5-dev libncursesw5-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev liblzma-dev

python3 -m pip install --upgrade pip
python3 -m pip install buildozer Cython==0.29.36

buildozer -v android debug
```

---

## Build e release no GitHub

O repositório já inclui workflow para **release Android**:

- arquivo: `.github/workflows/release.yml`
- gatilhos:
  - push de tags `v*`
  - execução manual via `workflow_dispatch`

O pipeline faz:
- validação da tag contra a versão do `buildozer.spec`
- execução dos testes
- build do APK
- assinatura do APK
- publicação em **GitHub Releases**

### Secrets esperados para release assinada

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

---

## Testes

Para rodar os testes locais:

```bash
python -m unittest discover -s tests -v
```

Alguns testes importantes do projeto cobrem:
- parser de histórico de XP
- navegação/back
- favoritos
- integrações
- hygiene do repositório
- hook do manifest para o serviço Android

---

## Permissões Android usadas

O app utiliza permissões compatíveis com o que ele faz hoje:

- `INTERNET`
- `POST_NOTIFICATIONS`
- `FOREGROUND_SERVICE`
- `FOREGROUND_SERVICE_DATA_SYNC`
- `WAKE_LOCK`
- `RECEIVE_BOOT_COMPLETED`

Essas permissões são usadas principalmente para:
- consultas online
- notificações
- monitoramento em segundo plano dos favoritos
- retomada automática do serviço no boot

---

## Observações importantes

- O app é **Android-first**.
- Algumas funções dependem de internet e de serviços de terceiros.
- O monitoramento em segundo plano pode se comportar diferente conforme a política de bateria/fundo de cada fabricante Android.
- Em versões mais novas do Android, o monitor de favoritos depende de configuração correta de **foreground service** no manifest e no serviço Python.
- O histórico de XP usa uma fonte auxiliar da comunidade e pode variar de disponibilidade.

---

## Estado atual do projeto

Entre os ajustes mais recentes da base:

- correção do serviço de favoritos para Androids mais novos
- estabilização do foreground service de notificações
- correção do parser do histórico de XP da aba Char
- melhorias no histórico de busca e navegação interna

---

## Autor

**Erick Bandeira**

Se quiser usar a checagem de updates e o botão de feedback, configure a URL do seu repositório GitHub em **Configurações** dentro do app.
