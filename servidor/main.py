# Servidor do Sussurros (versão 2: personagens criadas por ti).
#
# Criar uma personagem:
#   1. A app envia nome + obra para POST /personagens/gerar
#   2. A IA escreve a ficha (personalidade, forma de falar, primeira fala)
#   3. O servidor guarda-a como RASCUNHO e devolve-a para tu reveres
#   4. POST /personagens/{id}/guardar grava as tuas correções e ela vai para a galeria
#
# Conversar (igual à versão anterior):
#   1. A app envia o texto para POST /chat
#   2. O servidor junta ficha + regras + MEMÓRIA + RESUMO e as mensagens recentes
#   3. A IA responde pela ferramenta "responder": texto + escolhas + factos novos
#   4. Tudo fica guardado; as mensagens antigas vão sendo resumidas
#
# Onde fica tudo (pasta dados/<o teu id>/):
#   personagens/<id>.json   a ficha de cada personagem
#   conversas/<id>.json     a conversa, a memória e o resumo com essa personagem
#
# A chave da API fica SÓ aqui no servidor (ficheiro .env), nunca na app.

import json
import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# O .env tem de ser lido ANTES de importar o ia.py, porque é lá que está o PROVEDOR.
load_dotenv()

import ia  # noqa: E402  (a ligação à IA: Groq, OpenAI, Anthropic, Ollama)
from personagens import FERRAMENTA_FICHA, PEDIDO_FICHA, instrucoes  # noqa: E402

print(f"Sussurros | conversa: {ia.conversa.fornecedor} / {ia.conversa.modelo}"
      f" | fichas: {ia.fichas.fornecedor} / {ia.fichas.modelo}")

PASTA = Path(__file__).parent
DADOS = PASTA / "dados"
DADOS.mkdir(exist_ok=True)

JANELA = 24          # nº de mensagens recentes que a IA vê "palavra por palavra"
FOLGA = 10           # quando passarmos JANELA+FOLGA, as mais antigas vão para o resumo
MAX_FACTOS = 60
MAX_CARACTERES = 2000

app = FastAPI(title="Sussurros")

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


# ---------- Ficheiros ----------

def validar_id(valor: str) -> str:
    # Só letras, números e "-": impede ids manhosos tipo "../../" que
    # escreveriam fora da pasta dados/.
    if not re.fullmatch(r"[a-zA-Z0-9-]{8,64}", valor or ""):
        raise HTTPException(400, "Id inválido.")
    return valor


def pasta_de(utilizador: str, tipo: str) -> Path:
    p = DADOS / validar_id(utilizador) / tipo
    p.mkdir(parents=True, exist_ok=True)
    return p


def ler(f: Path):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def escrever(f: Path, dados) -> None:
    f.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def abrir_personagem(utilizador: str, pid: str) -> dict:
    p = ler(pasta_de(utilizador, "personagens") / f"{validar_id(pid)}.json")
    if not p:
        raise HTTPException(404, "Personagem não encontrada.")
    return p


def abrir_conversa(utilizador: str, p: dict) -> dict:
    conv = ler(pasta_de(utilizador, "conversas") / f"{p['id']}.json")
    return conv or {
        "mensagens": [{"papel": "personagem", "texto": p["saudacao"]}],
        "memoria": [], "resumo": "", "resumidas_ate": 0, "escolhas": [],
    }


def guardar_conversa(utilizador: str, pid: str, conv: dict) -> None:
    escrever(pasta_de(utilizador, "conversas") / f"{pid}.json", conv)


def cor(valor, padrao: str) -> str:
    return valor if isinstance(valor, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", valor) else padrao


def publico(p: dict) -> dict:
    """O que a app pode ver de uma personagem (o campo "menor" fica no servidor)."""
    return {k: p[k] for k in ("id", "nome", "obra", "frase", "ficha", "saudacao", "emoji", "cores", "conhecida")}


# ---------- Ajudas para a IA ----------

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
    # Enquanto testamos no PC, mostramos o erro real na página. Numa versão pública sai.
    return HTTPException(502, f"A IA não respondeu: {str(e)[:350]}")


def resumir_se_preciso(conv: dict, p: dict) -> None:
    """Quando a conversa fica longa, resume as mensagens mais antigas (assim a IA
    nunca recebe a conversa inteira, mas também não esquece o que aconteceu)."""
    msgs = conv["mensagens"]
    if len(msgs) - conv["resumidas_ate"] <= JANELA + FOLGA:
        return
    fim = len(msgs) - JANELA
    texto = "\n".join(
        f"{'Utilizador' if m['papel'] == 'utilizador' else p['nome']}: {m['texto']}"
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


# ---------- Pedidos que a app faz ----------

class PedidoGerar(BaseModel):
    utilizador: str
    nome: str
    obra: str = ""
    extra: str = ""


class PedidoGuardar(BaseModel):
    utilizador: str
    nome: str
    obra: str
    frase: str
    ficha: str
    saudacao: str


class PedidoChat(BaseModel):
    utilizador: str
    personagem: str
    texto: str


class PedidoSimples(BaseModel):
    utilizador: str
    personagem: str


# ---------- Personagens ----------

@app.get("/personagens")
def listar_personagens(utilizador: str):
    """As tuas personagens guardadas (sem rascunhos), da mais recente para a mais antiga."""
    pasta = pasta_de(utilizador, "personagens")
    lista = [ler(f) for f in sorted(pasta.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)]
    return [publico(p) for p in lista if p and not p.get("rascunho")]


@app.post("/personagens/gerar")
def gerar_personagem(pedido: PedidoGerar):
    nome = pedido.nome.strip()[:80]
    if not nome:
        raise HTTPException(400, "Escreve o nome da personagem.")
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

    p = {
        "id": uuid.uuid4().hex[:12],
        "rascunho": True,  # só passa para a galeria quando carregas em "Guardar"
        "nome": str(d.get("nome") or nome)[:80],
        "obra": str(d.get("obra") or pedido.obra)[:120],
        "frase": str(d.get("frase", ""))[:200],
        "ficha": str(d.get("ficha", "")),
        "saudacao": str(d.get("saudacao", "")) or "*olha para ti* Olá.",
        "emoji": str(d.get("emoji") or "✨")[:8],
        "cores": [cor(d.get("cor1"), "#3d2c5c"), cor(d.get("cor2"), "#c76b4a")],
        "conhecida": bool(d.get("conhecida", True)),
        # Na dúvida (ou se a IA não disser), trata como menor: mais vale prevenir.
        "menor": d.get("menor_na_obra") is not False,
    }
    escrever(pasta_de(pedido.utilizador, "personagens") / f"{p['id']}.json", p)
    return publico(p)


@app.post("/personagens/{pid}/guardar")
def guardar_personagem(pid: str, pedido: PedidoGuardar):
    """Grava as tuas correções à ficha. O campo "menor" NÃO vem da app:
    fica o que foi decidido quando a ficha foi gerada."""
    p = abrir_personagem(pedido.utilizador, pid)
    p.update({
        "nome": pedido.nome.strip()[:80] or p["nome"],
        "obra": pedido.obra.strip()[:120],
        "frase": pedido.frase.strip()[:200],
        "ficha": pedido.ficha.strip()[:4000] or p["ficha"],
        "saudacao": pedido.saudacao.strip()[:1000] or p["saudacao"],
        "rascunho": False,
    })
    escrever(pasta_de(pedido.utilizador, "personagens") / f"{pid}.json", p)
    return publico(p)


@app.post("/personagens/{pid}/apagar")
def apagar_personagem(pid: str, pedido: PedidoSimples):
    validar_id(pid)
    for tipo in ("personagens", "conversas"):
        f = pasta_de(pedido.utilizador, tipo) / f"{pid}.json"
        if f.exists():
            f.unlink()
    return {"ok": True}


# ---------- Conversa ----------

@app.get("/historia/{pid}")
def ver_historia(pid: str, utilizador: str):
    conv = abrir_conversa(utilizador, abrir_personagem(utilizador, pid))
    return {k: conv[k] for k in ("mensagens", "memoria", "resumo", "escolhas")}


@app.post("/chat")
def chat(pedido: PedidoChat):
    texto = pedido.texto.strip()
    if not texto or len(texto) > MAX_CARACTERES:
        raise HTTPException(400, "Mensagem vazia ou demasiado longa.")

    p = abrir_personagem(pedido.utilizador, pedido.personagem)
    conv = abrir_conversa(pedido.utilizador, p)
    conv["mensagens"].append({"papel": "utilizador", "texto": texto})

    try:
        # A ferramenta "responder" obriga a IA a responder sempre no mesmo formato.
        d = ia.conversa.estruturado(
            instrucoes(p, conv["memoria"], conv["resumo"]),
            para_api(conv["mensagens"][conv["resumidas_ate"]:]),
            FERRAMENTA_RESPOSTA,
        )
    except ia.ErroIA as e:
        raise erro_ia(e)

    resposta = str(d.get("resposta", "")).strip() or "*fica em silêncio por um momento*"
    escolhas = [str(e).strip() for e in d.get("escolhas", []) if str(e).strip()][:3]
    novos = [str(f).strip() for f in d.get("novos_factos", []) if str(f).strip()]

    ja = {f.lower() for f in conv["memoria"]}
    novos = [f for f in novos if f.lower() not in ja]
    conv["memoria"] = (conv["memoria"] + novos)[-MAX_FACTOS:]
    conv["mensagens"].append({"papel": "personagem", "texto": resposta})
    conv["escolhas"] = escolhas
    resumir_se_preciso(conv, p)
    guardar_conversa(pedido.utilizador, p["id"], conv)

    return {"resposta": resposta, "escolhas": escolhas, "novos_factos": novos}


@app.post("/recomecar")
def recomecar(pedido: PedidoSimples):
    f = pasta_de(pedido.utilizador, "conversas") / f"{validar_id(pedido.personagem)}.json"
    if f.exists():
        f.unlink()
    return {"ok": True}


@app.get("/modelos")
def modelos():
    """Diagnóstico: que IA está a ser usada e que modelos a tua conta tem."""
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
