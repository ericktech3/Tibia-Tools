<div align="center">

<img src="docs/github/banner.jpg" alt="Tibia Tools" width="100%">

# ⚔️ Tibia Tools

**A caixa de ferramentas do Tibia que cabe no bolso.**

Bosses, XP, stamina, treino, imbuements e a sua caçada —
tudo num app Android feito pela guild, para a guild.

[![CI](https://github.com/ericktech3/Tibia-Tools/actions/workflows/ci.yml/badge.svg)](https://github.com/ericktech3/Tibia-Tools/actions/workflows/ci.yml)
[![Release](https://github.com/ericktech3/Tibia-Tools/actions/workflows/release.yml/badge.svg)](https://github.com/ericktech3/Tibia-Tools/actions/workflows/release.yml)

[![Android](https://img.shields.io/badge/Android-APK%20direto-3DDC84?style=for-the-badge&logo=android&logoColor=white)](#-instalar-em-2-minutos)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](#-compilar)
[![Kivy + KivyMD](https://img.shields.io/badge/Kivy%20%2B%20KivyMD-1.2-00A0E8?style=for-the-badge)](#-como-o-app-funciona)
[![Testes](https://img.shields.io/badge/testes-129%20passando-4CAF50?style=for-the-badge)](#-qualidade)
[![Offline](https://img.shields.io/badge/offline-imbuements%20%2B%20cache-FF8F00?style=for-the-badge)](#-funciona-sem-internet)
[![Anúncios](https://img.shields.io/badge/an%C3%BAncios-zero-9E9E9E?style=for-the-badge)](#-por-que-ele-existe)

[Instalar](#-instalar-em-2-minutos) · [O que faz](#-o-que-voc%C3%AA-consegue-fazer) · [Compilar](#-compilar) · [Avisos](#%EF%B8%8F-aviso)

</div>

---

## 🤔 Por que ele existe?

Porque para responder cinco perguntas do dia a dia você abre dez abas:
*o boss aparece amanhã? quanta stamina falta? quanto custa treinar até o level 100?
esse imbuement vale os itens? quanto eu lucrei na caçada?*

O **Tibia Tools** junta tudo isso num app só: leve, em português,
sem cadastro, sem conta, sem anúncio e sem rastreador.
Funciona no celular e boa parte dele funciona **sem internet**.

---

## 📱 Instalar em 2 minutos

1. Abra a aba **[Releases](https://github.com/ericktech3/Tibia-Tools/releases)** deste repositório.
2. Baixe o arquivo `.apk` mais recente.
3. Toque no arquivo baixado e aceite a opção de **instalar apps desconhecidos**.
4. Pronto. Não precisa criar conta nem fazer login.

> Internet é usada só para: personagem, bosses, boosted e checagem de atualização.
> O resto (imbuements, stamina, treino, hunt, share XP) funciona no avião.

---

## ✨ O que você consegue fazer

| Aba | O que tem lá dentro |
| --- | --- |
| 🏠 **Home** | boosted do dia, último personagem consultado e seus bosses favoritos com chance alta |
| 🧙 **Char** | busca do personagem, XP dos últimos 30 dias, últimas mortes, chars da conta e Tibia Stalker |
| 🤝 **Share XP** | a faixa de level liberada para dividir experiência |
| ⭐ **Favoritos** | seus personagens salvos, com atalho para o Tibia.com |
| 🧰 **Mais** | bosses, boosted, treino, imbuements, stamina e hunt analyzer |
| ⚙️ **Configurações** | tema, avisos, serviço em segundo plano e atualização do app |

### 🧙 Char — o personagem por inteiro
- Busca por nome (fonte: **TibiaData v4**) com world, vocação, level e status.
- **XP dos últimos 30 dias** (fonte: GuildStats): total de 7 e 30 dias, média diária, melhor dia, dias ativos e atraso dos dados.
- **Últimas mortes**: data, nível, XP perdida e o motivo de cada uma.
- **Outros personagens da conta** — quando a Tibia informa.
- **Tibia Stalker**: sugestões de quem pode estar na mesma conta (probabilidade, não certeza).
- Um toque para **favoritar** ou abrir o personagem no **Tibia.com**.

### 🤝 Share XP
Informe seu level e veja na hora a faixa liberada para party share:
de ⌈2/3 do level⌉ até ⌊3/2 do level⌋.

### ⚔️ Bosses (ExevoPan)
- Lista completa por **world**, com a chance e **quantos dias faltam para aparecer**
  (ex.: *Ghazbaran — Sem chance · Aparecerá em: 6 dias*).
- Filtro por chance e modo **só favoritos**.
- Boss favorito pode **avisar quando estiver perto de aparecer**.
- Toque no nome para abrir a página do boss no **TibiaWiki BR**.

### ⭐ Boosted
Criatura e boss do dia, com sprite baixado e guardado no celular.

### 🏋️ Treino (Exercise)
Escolha a skill (melee, distance, shielding, magic, fist), a vocação e a arma
(Standard, Enhanced ou Lasting) e receba as **cargas necessárias**, o **custo em gp** e um resumo.

### 🧪 Imbuements — offline
Lista com busca, detalhe por tier (**Basic / Intricate / Powerful**), efeito e itens necessários.
Os dados vêm embutidos no APK: funciona sem internet.

### ⏳ Stamina
Informe a stamina atual e a desejada: o app diz **quanto tempo ficar offline** e
**em que horário** você chega lá, respeitando as regras reais de regeneração.

### 📊 Hunt Analyzer
Cole o texto da sessão de caça e receba **loot**, **supplies** e **balance** organizados.

### 🔔 Avisos e segundo plano
- Aviso quando o **boosted mudar** ou quando um **boss favorito ficar High**.
- **Monitorar favoritos com o app fechado** (serviço em primeiro plano do Android).
- Iniciar com o celular ligando, avisar quando ficar **online**, quando **upar level** ou quando **morrer**.
- Intervalo do monitor configurável.

### 🎨 Configurações
Tema claro ou escuro, limpeza de cache, e **checagem de atualização** direto no GitHub
com atalho para a página de releases.

---

## 🌐 Funciona sem internet?

Sim, em partes. As últimas respostas ficam guardadas no celular em um cache
seguro (JSON, sem pickle, com validade). Sem sinal, o app mostra o último dado
que ele tem e avisa a idade dele — por exemplo, *"dados de 10 minutos atrás"*.
Imbuements nunca precisa de rede.

---

## 🧱 Como o app funciona

```text
main.py                → composição do app e fluxos de tela
features/              → controllers por domínio (char, bosses, favoritos, settings)
core/                  → cálculos puros (stamina, treino, imbuements, hunt, share XP, cache)
integrations/          → TibiaData, Tibia.com, ExevoPan, Tibia Stalker, GitHub
integrations/parsers/  → leitura das páginas (ExevoPan, GuildStats) separada das chamadas
services/              → persistência, ponte com o Android, releases e relatórios de erro
ui/kv/                 → telas em KivyMD, um arquivo por tela
assets/                → ícone e tela de abertura
.github/workflows/     → testes (ci.yml), release assinada (release.yml), limpeza
buildozer.spec         → configuração do Buildozer
```

Regras do projeto ficam documentadas em [`AGENTS.md`](AGENTS.md) — leia antes de mexer.

---

## 🧪 Qualidade

- **129 testes automáticos** cobrindo cache, filtros de bosses, parsers, XP, mortes,
  navegação com o botão voltar, releases e a tela de personagem.
- A cada envio de código o GitHub roda sozinho:
  verificação de sintaxe, procura de nomes indefinidos, checagem dos arquivos `.kv`
  e a bateria de testes.
- Build Android fixa a versão do python-for-android para não quebrar do nada.

```bash
python -m unittest discover -s tests -v
```

---

## 🔨 Compilar

### Pelo GitHub (recomendado)
- **Push na `main`** → o workflow de release gera o APK como *artifact* para baixar.
- **Tag `v1.2`** → compila, **assina o APK** e publica em **GitHub Releases**.
  A tag precisa bater com a `version` do `buildozer.spec` (hoje `1.2`).

Secrets necessários para assinar a release:

| Secret | O que é |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | seu keystore `.jks` convertido em Base64 (`base64 -w0 meu.jks`) |
| `ANDROID_KEYSTORE_PASSWORD` | senha do keystore |
| `ANDROID_KEY_ALIAS` | nome da chave dentro do keystore |
| `ANDROID_KEY_PASSWORD` | senha da chave |

### No computador (Linux ou WSL2)
```bash
sudo apt update
sudo apt install -y python3 python3-pip git zip unzip openjdk-17-jdk \
  build-essential autoconf automake libtool pkg-config \
  libssl-dev libffi-dev libltdl-dev \
  libncurses5-dev libncursesw5-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev

python3 -m pip install --upgrade pip
python3 -m pip install buildozer cython==0.29.36
buildozer -v android debug
```

---

## 🩹 Deu errado?

Abra uma [issue](https://github.com/ericktech3/Tibia-Tools/issues) contando o que aconteceu e, se der, anexe o log
`tibia_tools_crash.log` (fica na pasta do app no celular).
Erros em tela de bosses, XP e personagem costumam ser mudança no site de origem —
são rápidos de corrigir assim que a gente vê o log.

## 🗺️ Ideias abertas

- Notificações de boss favorável no horário certo.
- Histórico de XP em gráfico.
- Mais idiomas e mais worlds.
- Temas por guild.

Pode abrir issue, sugerir ou mandar pull request — é bem-vindo.

---

## 🙏 Fontes de dados

[TibiaData](https://tibiadata.com) (personagem e boosted) ·
[GuildStats](https://guildstats.eu) (histórico de XP e mortes) ·
[Tibia.com](https://www.tibia.com) ·
[ExevoPan](https://www.exevopan.com) (bosses por world) ·
[TibiaWiki BR](https://tibiawiki.com.br) (páginas de boss) ·
[Tibia Stalker](https://www.tibiastalker.pl) (sugestões de conta)

---

## ⚠️ Aviso

Projeto **não-oficial**, de uso pessoal e de guild, sem afiliação com a CipSoft,
Tibia.com, TibiaWiki ou ExevoPan. Não vende nada, não coleta dados e não tem anúncios.
Os cálculos de treino, share XP e stamina são aproximações conferidas contra
referências da comunidade — use como apoio, não como garantia.
Sem licença definida no momento.

## 👤 Autor

**Erick Bandeira** — *Monk Curandeiro* · idealização, especificação, testes e manutenção.

<div align="center">

Feito com Kivy, KivyMD, Buildozer e muita teimosia. 🐉

</div>

<!--
  Capturas de tela: tire prints do app, salve em docs/screenshots/ e use o modelo abaixo.
  Uma linha por print:
  <img src="docs/screenshots/char.png" width="230" alt="Tela de personagem">
-->
