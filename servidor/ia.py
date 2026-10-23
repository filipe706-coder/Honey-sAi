# Ligação à IA. Este é o ÚNICO ficheiro que sabe que fornecedores usamos.
#
# Há duas "ligações", cada uma pode usar um fornecedor e modelo diferente:
#   ia.conversa  -> responde às mensagens (precisa de ser rápida)
#   ia.fichas    -> cria as fichas das personagens (precisa de conhecer as obras)
#
# Cada ligação tem duas funções:
#   .estruturado(system, mensagens, ferramenta) -> dict   resposta num formato JSON fixo
#   .texto(prompt)                              -> str    resposta em texto livre
#
# Configura-se no ficheiro .env:
#   PROVEDOR=groq            fornecedor da conversa (groq, openai, anthropic, ollama)
#   MODELO=...               modelo da conversa (opcional, há um por defeito)
#   PROVEDOR_FICHA=groq      fornecedor das fichas (se faltar, usa o PROVEDOR)
#   MODELO_FICHA=...         modelo das fichas (opcional)
#   + a chave de cada fornecedor: GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY

import json
import os
import re

# Para cada fornecedor: endereço, nome da variável com a chave,
# modelo de conversa por defeito e modelo de fichas por defeito.
FORNECEDORES = {
    "groq": {
        "url": "https://api.groq.com/openai/v1",
        "chave": "GROQ_API_KEY",
        # (vê os modelos da tua conta em http://localhost:8000/modelos)
        # O qwen/qwen3.8-27b é mais rápido mas falha o formato JSON com frequência.
        "modelos": ("openai/gpt-oss-120b", "openai/gpt-oss-120b"),
    },
    "openai": {
        "url": None,
        "chave": "OPENAI_API_KEY",
        "modelos": ("gpt-6-luna", "gpt-6-luna"),
    },
    "ollama": {
        "url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        "chave": None,  # o Ollama não precisa de chave
        "modelos": ("sussurros", "sussurros"),
    },
    "anthropic": {
        "url": None,
        "chave": "ANTHROPIC_API_KEY",
        "modelos": ("claude-haiku-5-5", "claude-sonnet-5-5"),
    },
}


class ErroIA(Exception):
    """Qualquer erro do fornecedor (chave errada, sem saldo, limite, modelo inexistente...)."""


def _ler_json(texto: str) -> dict:
    """Converte a resposta em dicionário, mesmo que venha dentro de ```json ... ```."""
    texto = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip()).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)  # último recurso: o primeiro {...}
        try:
            return json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            return {}


class LigacaoOpenAI:
    """Serve para OpenAI, Groq e Ollama: todos falam o "idioma" da OpenAI."""

    def __init__(self, fornecedor: str, modelo: str, esforco: str = "low"):
        import openai
        self._esforco = esforco
        self._erro = openai.OpenAIError
        self._erro_ligacao = openai.APIConnectionError
        cfg = FORNECEDORES[fornecedor]
        chave = os.getenv(cfg["chave"]) if cfg["chave"] else "ollama"
        if not chave:
            raise SystemExit(f"Falta a {cfg['chave']} no ficheiro servidor\\.env")
        self.fornecedor, self.modelo = fornecedor, modelo
        self._cliente = openai.OpenAI(base_url=cfg["url"], api_key=chave)
        # Modo de resposta estruturada:
        #   "funcao"  -> OpenAI: obriga a usar uma "function" (ferramenta)
        #   "esquema" -> Groq/Ollama: dá o esquema JSON e o servidor obriga a cumpri-lo
        #   "json"    -> plano B: só pede "JSON válido" e o esquema vai nas instruções
        self._modo = "funcao" if fornecedor == "openai" else "esquema"

    def _extras(self) -> dict:
        # Os modelos gpt-oss "pensam" antes de responder. Na conversa pensam pouco
        # (mais rápido); nas fichas pensam mais (menos erros sobre a obra).
        return {"reasoning_effort": self._esforco} if "gpt-oss" in self.modelo else {}

    def _pedir(self, **k):
        try:
            return self._cliente.chat.completions.create(model=self.modelo, **self._extras(), **k)
        except self._erro_ligacao as e:
            if self.fornecedor == "ollama":
                raise ErroIA("Não consegui falar com o Ollama. Está aberto? (ícone da lama ao pé do relógio)") from e
            raise ErroIA(f"Sem ligação a {self.fornecedor}: {e}") from e
        except self._erro as e:
            raise ErroIA(f"{type(e).__name__}: {e}") from e

    def estruturado(self, system, mensagens, ferramenta, max_tokens=800) -> dict:
        """Pede a resposta no formato da ferramenta. Se vier estragada (JSON inválido
        ou sem os campos obrigatórios), tenta mais uma vez antes de desistir."""
        obrigatorios = ferramenta["input_schema"].get("required", [])
        for tentativa in (1, 2):
            try:
                d = self._estruturado_uma_vez(system, mensagens, ferramenta, max_tokens)
            except ErroIA as e:
                if tentativa == 2 or "json_validate_failed" not in str(e):
                    raise
                print("Resposta com JSON inválido; a tentar outra vez.")
                continue
            if all(str(d.get(c, "")).strip() for c in obrigatorios if c not in ("escolhas", "novos_factos")):
                return d
            print("Resposta incompleta; a tentar outra vez.")
        return d

    def _estruturado_uma_vez(self, system, mensagens, ferramenta, max_tokens) -> dict:
        esquema = dict(ferramenta["input_schema"], additionalProperties=False)
        aviso = ("\n\nResponde APENAS com um objeto JSON com os campos: "
                 + ", ".join(esquema["properties"]) + ". Textos em português de Portugal.")

        if self._modo == "funcao":
            msgs = ([{"role": "system", "content": system}] if system else []) + mensagens
            r = self._pedir(
                max_completion_tokens=max_tokens, messages=msgs,
                tools=[{"type": "function", "function": {
                    "name": ferramenta["name"], "description": ferramenta["description"],
                    "parameters": esquema}}],
                tool_choice={"type": "function", "function": {"name": ferramenta["name"]}},
            )
            chamadas = r.choices[0].message.tool_calls or []
            return _ler_json(chamadas[0].function.arguments) if chamadas else {}

        msgs = [{"role": "system", "content": (system or "") + aviso}] + mensagens
        if self._modo == "esquema":
            try:
                r = self._pedir(
                    max_tokens=max_tokens, messages=msgs,
                    response_format={"type": "json_schema", "json_schema": {
                        "name": ferramenta["name"], "schema": esquema}},
                )
                return _ler_json(r.choices[0].message.content)
            except ErroIA as e:
                # Alguns modelos (ex: Llama no Groq) não aceitam esquemas: passamos
                # ao plano B e não voltamos a tentar o esquema com este modelo.
                if "json_schema" not in str(e) and "response_format" not in str(e):
                    raise
                print(f"{self.modelo} não aceita esquemas JSON; a usar o modo JSON simples.")
                self._modo = "json"

        r = self._pedir(max_tokens=max_tokens, messages=msgs, response_format={"type": "json_object"})
        return _ler_json(r.choices[0].message.content)

    def texto(self, prompt, max_tokens=600) -> str:
        r = self._pedir(max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return (r.choices[0].message.content or "").strip()

    def listar_modelos(self) -> list[str]:
        """Os modelos a que a tua conta tem acesso (útil para escolher no .env)."""
        try:
            return sorted(m.id for m in self._cliente.models.list())
        except self._erro as e:
            raise ErroIA(f"{type(e).__name__}: {e}") from e


class LigacaoAnthropic:
    def __init__(self, fornecedor: str, modelo: str):
        import anthropic
        self._anthropic = anthropic
        self.fornecedor, self.modelo = fornecedor, modelo
        self._cliente = anthropic.Anthropic()

    def _pedir(self, **k):
        try:
            return self._cliente.messages.create(model=self.modelo, **k)
        except self._anthropic.APIError as e:
            raise ErroIA(f"{type(e).__name__}: {e}") from e

    def estruturado(self, system, mensagens, ferramenta, max_tokens=800) -> dict:
        extra = {"system": system} if system else {}
        r = self._pedir(max_tokens=max_tokens, messages=mensagens, tools=[ferramenta],
                        tool_choice={"type": "tool", "name": ferramenta["name"]}, **extra)
        return next((b.input for b in r.content if b.type == "tool_use"), {})

    def texto(self, prompt, max_tokens=600) -> str:
        r = self._pedir(max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if b.type == "text").strip()


def _ligar(var_provedor: str, var_modelo: str, indice: int, padrao: str, esforco: str):
    fornecedor = (os.getenv(var_provedor) or padrao).lower()
    if fornecedor not in FORNECEDORES:
        raise SystemExit(f"{var_provedor}={fornecedor} não existe. Opções: {', '.join(FORNECEDORES)}")
    modelo = os.getenv(var_modelo) or FORNECEDORES[fornecedor]["modelos"][indice]
    if fornecedor == "anthropic":
        return LigacaoAnthropic(fornecedor, modelo)
    return LigacaoOpenAI(fornecedor, modelo, esforco)


conversa = _ligar("PROVEDOR", "MODELO", 0, "groq", "low")
fichas = _ligar("PROVEDOR_FICHA", "MODELO_FICHA", 1, conversa.fornecedor, "medium")
