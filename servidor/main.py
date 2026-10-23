# Servidor do Sussurros (versão 3: os dados ficam no browser).
#
# O servidor já NÃO guarda personagens nem conversas: isso fica no browser de
# cada pessoa (localStorage). Assim pode correr num servidor grátis que apaga
# os ficheiros quando reinicia (como o Render), e cada pessoa tem os seus dados.
# O servidor só faz três coisas:
#   1. guarda a chave da IA (que nunca pode ir para o browser)
#   2. fala com a IA (criar fichas e responder às mensagens)
#   3. protege a app (palavra-passe, limites por dia, regra de menores)
#
# Criar uma personagem:  POST /personagens/gerar  -> devolve a ficha + um "selo"
# Conversar:             POST /chat  -> o browser envia a ficha, a conversa e a
#                        mensagem nova; o servidor devolve a conversa atualizada
#
# O "selo": quando a IA cria a ficha, decide se a personagem é menor na obra.
# O servidor assina essa decisão com um SEGREDO que só ele conhece (HMAC).
# O browser guarda o selo e envia-o em cada mensagem. Se alguém o alterar, a
# assinatura deixa de bater certo e o servidor trata a personagem como menor.

import datetime
import hashlib
import hmac
import os
import re
import secrets
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

# O .env tem de ser lido ANTES de importar o ia.py, porque é lá que está o PROVEDOR.
load_dotenv()

import ia  # noqa: E402  (a ligação à IA: Groq, OpenAI, Anthropic, Ollama)
from personagens import FERRAMENTA_FICHA, PEDIDO_FICHA, instrucoes  # noqa: E402

print(f"Sussurros | conversa: {ia.conversa.fornecedor} / {ia.conversa.modelo}"
      f" | fichas: {ia.fichas.fornecedor} / {ia.fichas.modelo}")

PASTA = Path(__file__).parent

JANELA = 24          # nº de mensagens recentes que a IA vê "palavra por palavra"
FOLGA = 10           # quando passarmos JANELA+FOLGA, as mais antigas vão para o resumo
MAX_FACTOS = 60
MAX_CARACTERES = 2000
# Limites de pedidos à IA por dia, para a quota do Groq nunca se esgotar:
MAX_PEDIDOS_DIA = int(os.getenv("MAX_PEDIDOS_DIA", "300"))           # por pessoa
MAX_PEDIDOS_DIA_TOTAL = int(os.getenv("MAX_PEDIDOS_DIA_TOTAL", "1000"))  # todos juntos

app = FastAPI(title="Sussurros")


# ---------- Segredo para assinar os selos ----------
# No Render vem da variável SEGREDO. No PC, se não existir, criamos um e
# guardamo-lo num ficheiro, para os selos continuarem válidos depois de reiniciar.

def obter_segredo() -> str:
    if os.getenv("SEGREDO"):
        return os.environ["SEGREDO"]
    f = PASTA / "dados" / "segredo.txt"
    if f.exists():
        return f.read_text().strip()
    f.parent.mkdir(exist_ok=True)
    novo = secrets.token_hex(32)
    f.write_text(novo)
    return novo


SEGREDO = obter_segredo().encode()


def fazer_selo(pid: str, menor: bool) -> str:
    valor = "1" if menor else "0"
    assinatura = hmac.new(SEGREDO, f"{pid}:{valor}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{valor}.{assinatura}"


def e_menor(pid: str, selo: str) -> bool:
    """Lê o selo. Se for inválido ou tiver sido mexido, trata como menor (mais seguro)."""
    for menor in (False, True):
        if hmac.compare_digest(selo or "", fazer_selo(pid, menor)):
            return menor
    return True


# ---------- Palavra-passe de acesso ----------
# Se houver SENHA (no .env ou nas variáveis do Render), só entra quem a souber.
# Quem acerta fica com um "cookie" no browser durante 30 dias.
# O cookie guarda uma impressão digital (hash) da senha, nunca a senha em si.

SENHA = os.getenv("SENHA", "").strip()
COOKIE = "sussurros_acesso"


def impressao(senha: str) -> str:
    return hashlib.sha256(("sussurros:" + senha).encode()).hexdigest()


PAGINA_ENTRAR = """<!doctype html><html lang="pt"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Sussurros</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#120d14;color:#f3eaf0;
font-family:system-ui,sans-serif}form{width:min(320px,90vw);display:grid;gap:12px;text-align:center}
h1{font-family:Georgia,serif;font-weight:600;margin:0 0 8px}input,button{font:inherit;padding:12px 14px;
border-radius:14px;border:1px solid #2e2432;background:#1d1620;color:inherit}button{background:#e7a0b4;
color:#2a1020;border:0;font-weight:600;cursor:pointer}p{color:#ff8a9a;margin:0;font-size:14px}</style>
</head><body><form method="post" action="/entrar"><h1>Sussurros</h1>
<input type="password" name="senha" placeholder="Palavra-passe" autofocus required>
<button>Entrar</button>__ERRO__</form></body></html>"""


@app.middleware("http")
async def exigir_senha(request: Request, chamar):
    if not SENHA or request.url.path == "/entrar":
        return await chamar(request)
    if hmac.compare_digest(request.cookies.get(COOKIE, ""), impressao(SENHA)):
        return await chamar(request)
    if request.method == "GET" and request.url.path in ("/", "/conversa"):
        return HTMLResponse(PAGINA_ENTRAR.replace("__ERRO__", ""))
    return JSONResponse({"detail": "Precisas da palavra-passe. Recarrega a página."}, status_code=401)


@app.post("/entrar")
def entrar(senha: str = Form("")):
    if not SENHA or not hmac.compare_digest(senha.strip(), SENHA):
        return HTMLResponse(PAGINA_ENTRAR.replace("__ERRO__", "<p>Palavra-passe errada.</p>"), status_code=401)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie(COOKIE, impressao(SENHA), max_age=30 * 24 * 3600, httponly=True, samesite="lax")
    return r


# ---------- Limites por dia (guardados em memória) ----------
# Se o servidor reiniciar, a contagem recomeça. Não faz mal: é só uma proteção.

_uso: dict[str, int] = {}
_uso_dia = ""


def contar_pedido(utilizador: str) -> None:
    global _uso, _uso_dia
    if not re.fullmatch(r"[a-zA-Z0-9-]{8,64}", utilizador or ""):
        raise HTTPException(400, "Id inválido.")
    hoje = datetime.date.today().isoformat()
    if hoje != _uso_dia:
        _uso, _uso_dia = {}, hoje
    if _uso.get("*", 0) >= MAX_PEDIDOS_DIA_TOTAL:
        raise HTTPException(429, "A app chegou ao limite de mensagens de hoje. Volta amanhã!")
    if _uso.get(utilizador, 0) >= MAX_PEDIDOS_DIA:
        raise HTTPException(429, f"Chegaste ao limite de {MAX_PEDIDOS_DIA} mensagens por hoje. Volta amanhã!")
    _uso[utilizador] = _uso.get(utilizador, 0) + 1
    _uso["*"] = _uso.get("*", 0) + 1


# ---------- Ajudas ----------

FERRAMENTA_RESPOSTA = {
    "name": "responder",
    "description": "Envia a tua fala, 3 escolhas para o utilizador e factos novos.",
    "input_schema": {
        "type": "object",
        "properties": {
            "resposta": {"type": "string"},
            "escolhas": {"type": "array", "items": {"type": "string"}},
            "novos_factos": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["resposta", "escolhas", "novos_factos"],
    },
}


def cor(valor, padrao: str) -> str:
    return valor if isinstance(valor, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", valor) else padrao


def para_api(mensagens: list[dict]) -> list[dict]:
    """Formato da API: "user"/"assistant", a começar em "user" e a alternar."""
    out: list[dict] = []
    for m in mensagens:
        role = "user" if m["papel"] == "utilizador" else "assistant"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + m["texto"]
        else:
            out.append({"role": role, "content": m["texto"]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def erro_ia(e: Exception):
    print("Erro da API:", e)
    return HTTPException(502, f"A IA não respondeu: {str(e)[:350]}")


def resumir_se_preciso(conv: dict, nome: str) -> None:
    """Quando a conversa fica longa, resume as mensagens mais antigas (assim a IA
    nunca recebe a conversa inteira, mas também não esquece o que aconteceu)."""
    msgs = conv["mensagens"]
    if len(msgs) - conv["resumidas_ate"] <= JANELA + FOLGA:
        return
    fim = len(msgs) - JANELA
    texto = "\n".join(
        f"{'Utilizador' if m['papel'] == 'utilizador' else nome}: {m['texto']}"
        for m in msgs[conv["resumidas_ate"]:fim]
    )
    try:
        resumo = ia.conversa.texto((
            f"Resumo atual da conversa:\n{conv['resumo'] or '(vazio)'}\n\nNovas partes:\n{texto}\n\n"
            "Escreve um novo resumo completo em português de Portugal, no máximo 200 palavras, "
            "focado nos acontecimentos, emoções e na evolução da relação. Responde só com o resumo."
        ))
        if resumo:
            conv["resumo"] = resumo
            conv["resumidas_ate"] = fim
    except ia.ErroIA as e:
        print("Erro ao resumir (tenta-se outra vez na próxima):", e)


# ---------- O que o browser envia ----------
# Os limites de tamanho (max_length) impedem que alguém mande coisas gigantes.

class Mensagem(BaseModel):
    papel: str = Field(pattern="^(utilizador|personagem)$")
    texto: str = Field(max_length=6000)


class Conversa(BaseModel):
    mensagens: list[Mensagem] = Field(max_length=2000)
    memoria: list[str] = Field(default_factory=list, max_length=200)
    resumo: str = Field(default="", max_length=6000)
    resumidas_ate: int = 0


class Personagem(BaseModel):
    id: str = Field(pattern="^[a-f0-9]{12}$")
    nome: str = Field(max_length=80)
    obra: str = Field(default="", max_length=120)
    ficha: str = Field(max_length=4000)
    saudacao: str = Field(max_length=1000)
    selo: str = Field(default="", max_length=64)


class PedidoGerar(BaseModel):
    utilizador: str
    nome: str
    obra: str = ""
    extra: str = ""


class PedidoChat(BaseModel):
    utilizador: str
    personagem: Personagem
    conversa: Conversa
    texto: str


# ---------- Pedidos ----------

@app.post("/personagens/gerar")
def gerar_personagem(pedido: PedidoGerar):
    nome = pedido.nome.strip()[:80]
    if not nome:
        raise HTTPException(400, "Escreve o nome da personagem.")
    contar_pedido(pedido.utilizador)
    try:
        d = ia.fichas.estruturado(
            None,
            [{"role": "user", "content": PEDIDO_FICHA.format(
                nome=nome, obra=pedido.obra.strip()[:120] or "(não indicada)",
                extra=pedido.extra.strip()[:1000] or "(nenhuma)")}],
            FERRAMENTA_FICHA, max_tokens=3000,
        )
    except ia.ErroIA as e:
        raise erro_ia(e)
    if not d:
        raise HTTPException(502, "A IA não conseguiu criar a ficha. Tenta outra vez.")

    pid = uuid.uuid4().hex[:12]
    # Na dúvida (ou se a IA não disser), trata como menor: mais vale prevenir.
    menor = d.get("menor_na_obra") is not False
    return {
        "id": pid,
        "nome": str(d.get("nome") or nome)[:80],
        "obra": str(d.get("obra") or pedido.obra)[:120],
        "frase": str(d.get("frase", ""))[:200],
        "ficha": str(d.get("ficha", ""))[:4000],
        "saudacao": str(d.get("saudacao", ""))[:1000] or "*olha para ti* Olá.",
        "emoji": str(d.get("emoji") or "✨")[:8],
        "cores": [cor(d.get("cor1"), "#3d2c5c"), cor(d.get("cor2"), "#c76b4a")],
        "conhecida": bool(d.get("conhecida", True)),
        "selo": fazer_selo(pid, menor),
    }


@app.post("/chat")
def chat(pedido: PedidoChat):
    texto = pedido.texto.strip()
    if not texto or len(texto) > MAX_CARACTERES:
        raise HTTPException(400, "Mensagem vazia ou demasiado longa.")
    contar_pedido(pedido.utilizador)

    p = pedido.personagem.model_dump()
    p["menor"] = e_menor(p["id"], p["selo"])

    conv = pedido.conversa.model_dump()
    conv["memoria"] = [str(f)[:300] for f in conv["memoria"]][-MAX_FACTOS:]
    conv["resumidas_ate"] = max(0, min(conv["resumidas_ate"], len(conv["mensagens"])))
    conv["mensagens"].append({"papel": "utilizador", "texto": texto})

    try:
        d = ia.conversa.estruturado(
            instrucoes(p, conv["memoria"], conv["resumo"]),
            para_api(conv["mensagens"][conv["resumidas_ate"]:]),
            FERRAMENTA_RESPOSTA,
        )
    except ia.ErroIA as e:
        raise erro_ia(e)

    resposta = str(d.get("resposta", "")).strip() or "*fica em silêncio por um momento*"
    escolhas = [str(e).strip() for e in d.get("escolhas", []) if str(e).strip()][:3]
    novos = [str(f).strip()[:300] for f in d.get("novos_factos", []) if str(f).strip()]

    ja = {f.lower() for f in conv["memoria"]}
    novos = [f for f in novos if f.lower() not in ja]
    conv["memoria"] = (conv["memoria"] + novos)[-MAX_FACTOS:]
    conv["mensagens"].append({"papel": "personagem", "texto": resposta})
    resumir_se_preciso(conv, p["nome"])

    return {"resposta": resposta, "escolhas": escolhas, "novos_factos": novos, "conversa": conv}


@app.get("/modelos")
def modelos():
    """Diagnóstico: que IA está a ser usada e que modelos a conta tem."""
    info = {"conversa": f"{ia.conversa.fornecedor} / {ia.conversa.modelo}",
            "fichas": f"{ia.fichas.fornecedor} / {ia.fichas.modelo}"}
    try:
        info["disponiveis"] = ia.conversa.listar_modelos() if hasattr(ia.conversa, "listar_modelos") else "?"
    except ia.ErroIA as e:
        info["disponiveis"] = str(e)
    return info


@app.get("/", response_class=HTMLResponse)
@app.get("/conversa", response_class=HTMLResponse)
def pagina():
    return (PASTA / "app.html").read_text(encoding="utf-8")
