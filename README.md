# Sussurros

App de conversas com personagens, com IA. Escolhes uma personagem de um anime,
série, livro ou jogo (ou inventas uma tua), a IA cria-lhe a personalidade e a
forma de falar, e depois conversas com ela. A personagem lembra-se de ti: do
teu nome, do que gostas, do que já aconteceu entre vocês.

Usa-se no browser (PC ou telemóvel). As personagens e conversas ficam guardadas
no br## Pôr online com um link fixo (Render, grátis)

O Render liga-se a este repositório do GitHub, corre o servidor e dá um link
fixo tipo `https://honey-sai.onrender.com`. Sempre que fizerem push para o
`main`, o site atualiza sozinho.

1. Entra em https://render.com com **"Sign in with GitHub"**.
2. **New → Blueprint** e escolhe o repositório **Honey-sAi**
   (se não aparecer, dá acesso ao Render a este repositório quando o GitHub pedir).
3. O Render lê o `render.yaml` e pede dois valores:
   - `GROQ_API_KEY`: a chave do Groq
   - `SENHA`: a palavra-passe para entrar na app
4. **Deploy**. Ao fim de uns minutos aparece o link no topo da página do serviço.

No plano grátis o servidor "adormece" depois de 15 minutos sem uso; a primeira
visita a seguir demora ~1 minuto a acordar. Como os dados ficam no browser de
cada pessoa, nada se perde quando ele reinicia.

**Cópias de segurança:** como as conversas vivem no browser, limpar os dados
do browser apaga-as. Na galeria há **Exportar cópia** (guarda um ficheiro) e
**Importar** (também serve para passar as personagens para outro aparelho).

---

owser de cada pessoa; o servidor só fala com a IA.

---

## Pôr a correr (Windows)

Precisas de:
- **Python** – https://www.python.org/downloads/
  No primeiro ecrã do instalador, marca **"Add python.exe to PATH"**.
- **Uma chave do Groq** (grátis) – cria conta em https://console.groq.com e
  depois uma chave em https://console.groq.com/keys

Depois:
1. Descarrega o projeto (botão verde **Code → Download ZIP** no GitHub, ou `git clone`).
2. Dá **duplo clique no `iniciar.bat`**.
3. Na primeira vez instala tudo sozinho e pede-te a chave do Groq. Cola-a com
   clique direito na janela preta e carrega Enter.
4. O browser abre em http://localhost:8000. A janela preta tem de ficar aberta
   enquanto usas a app (é o servidor).

A chave fica só no ficheiro `servidor/.env` do teu PC. **Nunca a partilhes nem
a ponhas no GitHub** (o `.env` está no `.gitignore` para isso não acontecer).
Cada pessoa usa a sua própria chave.

---

## Partilhar a partir do PC (alternativa ao Render)

O `partilhar.bat` cria um link público tipo `https://algo.trycloudflare.com`
para outra pessoa usar a app a partir do telemóvel ou de outro PC.

1. Fecha a janela preta do servidor, se estiver aberta.
2. Duplo clique no **`partilhar.bat`**.
   - Na 1.ª vez oferece-se para instalar o `cloudflared` (programa grátis da
     Cloudflare que cria o túnel). Depois disso fecha e volta a abrir.
   - Pede uma **palavra-passe de acesso** (usa só letras e números) e guarda-a
     como `SENHA=` no `servidor/.env`.
3. Abre-se uma janela nova com o servidor, e na janela do partilhar aparece
   uma linha com o link `https://....trycloudflare.com`.
4. Envia o link **e a palavra-passe** a quem quiseres. Quem entra fica com
   acesso durante 30 dias nesse browser.

Atenção:
- O PC tem de estar ligado, com as duas janelas abertas.
- O link muda de cada vez que corres o `partilhar.bat`.
- Cada pessoa tem as suas próprias personagens e conversas, guardadas no
  browser dela.
- Há limites de pedidos à IA por dia: 300 por pessoa (`MAX_PEDIDOS_DIA`) e 1000
  no total (`MAX_PEDIDOS_DIA_TOTAL`).

---

## Como se usa

**Criar uma personagem**
1. Carrega em **Criar personagem**.
2. Escreve o nome e a obra (ex: "L" e "Death Note"). As notas são opcionais.
   Para uma personagem tua, deixa a obra vazia e descreve-a nas notas.
3. A IA gera a ficha: personalidade, forma de falar, 4 exemplos de falas e a
   primeira fala. Revê, corrige o que quiseres e carrega em **Guardar e conversar**.

**Conversar**
- A conversa flui naturalmente, sem guiões.
- 🧠 mostra o que a personagem se lembra de ti e um resumo da conversa.
  Quando ela aprende algo novo aparece um aviso "✦ vai lembrar-se disto".
- 💡 liga/desliga sugestões de resposta.
- No painel 🧠 podes recomeçar a conversa ou apagar a personagem.

**Regra fixa:** personagens que são menores de idade na obra original nunca
entram em romance (amizade, aventura, mistério, etc. sim). A IA identifica isso
ao criar a ficha e a regra fica no servidor, mesmo que a ficha seja editada.

---

## Como funciona (para quem mexe no código)

```
Browser (app.html) ──▶ Servidor Python (main.py) ──▶ IA (Groq, via ia.py)
   │
   └── localStorage: personagens e conversas (cada pessoa tem as suas)
```

O servidor não guarda nada. Em cada mensagem, o browser envia a ficha, a
conversa e a memória; o servidor pergunta à IA e devolve a conversa atualizada.

**Regra de menores e o "selo":** ao criar a ficha, a IA diz se a personagem é
menor na obra. O servidor assina essa decisão com um `SEGREDO` (HMAC) e o
browser guarda o selo. Se alguém o alterar, a assinatura deixa de bater certo
e o servidor trata a personagem como menor.

| Ficheiro | O que faz |
|---|---|
| `servidor/app.html` | A interface: galeria, criar personagem, chat, memória |
| `servidor/main.py` | O servidor: criar/guardar personagens, conversa, memória, resumo |
| `servidor/personagens.py` | Os textos para a IA: como gerar fichas e as regras da conversa |
| `servidor/ia.py` | A ligação à IA. É o único ficheiro que sabe que fornecedor usamos |
| `iniciar.bat` | Instala e arranca tudo |
| `partilhar.bat` | Cria um link público (túnel Cloudflare) protegido por palavra-passe |
| `render.yaml` | Configuração para pôr online no Render |
| `iniciar-ollama.bat` | Alternativa: arranca com uma IA local (Ollama) em vez do Groq |
| `app/` | Primeira versão da app Android (desatualizada, vai ser refeita) |

**Uma mensagem, passo a passo**
1. O browser envia o texto para `POST /chat`.
2. O servidor junta a ficha da personagem, as regras, a **memória** (lista de
   factos) e o **resumo**, mais as últimas 24 mensagens.
3. A IA responde num formato JSON fixo: a fala, 3 sugestões e os factos novos.
4. O servidor guarda tudo. Quando a conversa fica longa, as mensagens antigas
   são resumidas, para a IA nunca receber a conversa inteira (ficaria lenta).

**Mudar de IA** – no `servidor/.env` (se uma linha aparecer duas vezes, conta a última):
- `PROVEDOR=` conversa: `groq`, `openai`, `anthropic` ou `ollama`
- `PROVEDOR_FICHA=` fichas (se faltar, usa o mesmo)
- `MODELO=` / `MODELO_FICHA=` para trocar de modelo
- a chave de cada um: `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

Os modelos que a tua conta do Groq tem aparecem em http://localhost:8000/modelos.
Por defeito usamos `openai/gpt-oss-120b` para tudo (o `qwen/qwen3.8-27b` é mais
rápido, mas falhou o formato das respostas nos testes).

Ao arrancar, a janela preta mostra que fornecedor e modelos está a usar.

**IA local (Ollama)** – grátis, sem limites e sem internet, mas mais fraca:
instala o Ollama (https://ollama.com/download), abre-o uma vez e usa o
`iniciar-ollama.bat`. Na primeira vez descarrega o modelo (~4.7 GB).

---

## Limites atuais (de propósito)
- Sem contas: cada browser tem as suas personagens. Para mudar de aparelho, usa Exportar/Importar.
- A proteção é uma palavra-passe partilhada (`SENHA`), suficiente para uso
  entre amigos, não para uma app pública.
- Os erros da IA aparecem detalhados na página (útil para testar).

## Próximos passos
- Contas de utilizador a sério
- App Android
- Imagens das personagens
