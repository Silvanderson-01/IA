"""
Fantasma - bolsa de valores: cotações da B3 e carteira SIMULADA (dinheiro fictício).

Dados: brapi.dev (plano gratuito, ~30 minutos de atraso). Sem token, só funcionam
PETR4, VALE3, MGLU3 e ITUB4. Para os demais, crie uma conta gratuita em brapi.dev
e salve o token no arquivo brapi_token.txt (na mesma pasta).

NADA aqui envia ordens reais. A simulação não inclui corretagem, impostos nem a
diferença de preço entre a decisão e a execução, então é mais otimista que a realidade.
"""

import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).parent
ARQUIVO = PASTA / "carteira.json"          # carteira e histórico da simulação
ARQUIVO_TOKEN = PASTA / "brapi_token.txt"  # token gratuito da brapi.dev
CAIXA_INICIAL = 100_000.0                  # dinheiro fictício inicial
ATIVOS_TESTE = {"PETR4", "VALE3", "MGLU3", "ITUB4"}  # funcionam sem token

# Nomes falados -> código na B3 (acrescente os seus)
NOMES = {
    "petrobras": "PETR4", "vale": "VALE3", "itau": "ITUB4", "itau unibanco": "ITUB4",
    "magazine luiza": "MGLU3", "magalu": "MGLU3", "banco do brasil": "BBAS3",
    "bradesco": "BBDC4", "ambev": "ABEV3", "weg": "WEGE3", "b3": "B3SA3",
    "suzano": "SUZB3", "itausa": "ITSA4", "localiza": "RENT3", "eletrobras": "ELET3",
    "embraer": "EMBR3", "gerdau": "GGBR4", "sabesp": "SBSP3", "jbs": "JBSS3",
}


class ErroBolsa(Exception):
    pass


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto)
    return "".join(c for c in base if unicodedata.category(c) != "Mn").lower().strip()


def _reais(valor: float) -> str:  # formato fácil de falar em voz alta
    return f"{valor:.2f}".replace(".", ",") + " reais"


def _resultado(valor: float) -> str:  # "lucro de X" ou "prejuízo de X", fácil de falar
    return f"{'lucro' if valor >= 0 else 'prejuízo'} de {_reais(abs(valor))}"


def _pct(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + " por cento"


# ---------------- Cotações ----------------

def _ticker(ativo) -> str:
    chave = _sem_acento(str(ativo))
    if chave in NOMES:
        return NOMES[chave]
    for nome, codigo in NOMES.items():
        if nome in chave:
            return codigo
    codigo = str(ativo).strip().upper().replace(".SA", "")
    if not re.fullmatch(r"[A-Z]{4}\d{1,2}", codigo):
        raise ErroBolsa(f"Não reconheci o ativo '{ativo}'. Diga o nome da empresa ou o código, como PETR4.")
    return codigo


def _token() -> str:
    token = os.environ.get("BRAPI_TOKEN", "").strip()
    if not token and ARQUIVO_TOKEN.exists():
        token = ARQUIVO_TOKEN.read_text(encoding="utf-8").strip()
    return token


def _buscar(ticker: str) -> dict:
    cabecalhos = {"User-Agent": "Fantasma/1.0"}
    token = _token()
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    pedido = urllib.request.Request(f"https://brapi.dev/api/quote/{urllib.parse.quote(ticker)}",
                                    headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 402, 403) and not token and ticker not in ATIVOS_TESTE:
            raise ErroBolsa(f"Para consultar {ticker} é preciso um token gratuito da brapi ponto dev. "
                            "Salve o token no arquivo brapi_token.txt.")
        if erro.code == 404:
            raise ErroBolsa(f"Não encontrei o ativo {ticker}.")
        raise ErroBolsa(f"A brapi respondeu com o erro {erro.code}.")
    except Exception as erro:
        raise ErroBolsa(f"Não consegui acessar a brapi. Verifique a internet. ({erro})")
    resultados = dados.get("results") or []
    if not resultados:
        raise ErroBolsa(f"Não encontrei dados para {ticker}.")
    return resultados[0]


def _preco(resultado: dict) -> float:
    preco = resultado.get("regularMarketPrice")
    if preco is None:
        raise ErroBolsa("A cotação veio sem preço.")
    return float(preco)


def cotacao(ativo="PETR4") -> str:
    try:
        ticker = _ticker(ativo)
        r = _buscar(ticker)
        texto = f"{r.get('shortName') or ticker} ({ticker}): {_reais(_preco(r))}"
        variacao = r.get("regularMarketChangePercent")
        if variacao is not None:
            texto += f", {'alta' if variacao >= 0 else 'queda'} de {_pct(abs(float(variacao)))} no dia"
        return texto + ". Cotação com atraso de cerca de 30 minutos."
    except ErroBolsa as erro:
        return str(erro)


# ---------------- Carteira simulada ----------------

def _carregar() -> dict:
    if ARQUIVO.exists():
        try:
            return json.loads(ARQUIVO.read_text(encoding="utf-8"))
        except ValueError:  # arquivo corrompido: guarda uma cópia e recomeça
            ARQUIVO.replace(ARQUIVO.with_name("carteira_corrompida.json"))
    return {"caixa_inicial": CAIXA_INICIAL, "caixa": CAIXA_INICIAL, "posicoes": {}, "historico": []}


def _salvar(carteira: dict):
    temporario = ARQUIVO.with_suffix(".tmp")
    temporario.write_text(json.dumps(carteira, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(ARQUIVO)


def _quantidade(valor) -> int:
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        raise ErroBolsa("Não entendi a quantidade.")
    if n <= 0:
        raise ErroBolsa("A quantidade precisa ser maior que zero.")
    return n


def _registrar(carteira, tipo, ticker, qtd, preco, motivo, lucro=None):
    item = {"data": datetime.now().strftime("%Y-%m-%d %H:%M"), "tipo": tipo, "ativo": ticker,
            "qtd": qtd, "preco": preco, "motivo": str(motivo or "")[:200]}
    if lucro is not None:
        item["lucro"] = lucro
    carteira["historico"].append(item)


def comprar_simulado(ativo, quantidade, motivo="") -> str:
    try:
        ticker, qtd = _ticker(ativo), _quantidade(quantidade)
        preco = _preco(_buscar(ticker))
        carteira = _carregar()
        custo = preco * qtd
        if custo > carteira["caixa"]:
            return (f"Saldo insuficiente na simulação: custaria {_reais(custo)} "
                    f"e há {_reais(carteira['caixa'])} em caixa.")
        pos = carteira["posicoes"].get(ticker, {"qtd": 0, "preco_medio": 0.0})
        nova_qtd = pos["qtd"] + qtd
        pos["preco_medio"] = (pos["qtd"] * pos["preco_medio"] + custo) / nova_qtd
        pos["qtd"] = nova_qtd
        carteira["posicoes"][ticker] = pos
        carteira["caixa"] -= custo
        _registrar(carteira, "compra", ticker, qtd, preco, motivo)
        _salvar(carteira)
        return (f"Simulação: comprei {qtd} de {ticker} a {_reais(preco)} cada, total de {_reais(custo)}. "
                f"Sobram {_reais(carteira['caixa'])} em caixa.")
    except ErroBolsa as erro:
        return str(erro)


def vender_simulado(ativo, quantidade, motivo="") -> str:
    try:
        ticker, qtd = _ticker(ativo), _quantidade(quantidade)
        carteira = _carregar()
        pos = carteira["posicoes"].get(ticker)
        if not pos or pos["qtd"] < qtd:
            tem = pos["qtd"] if pos else 0
            return f"Na simulação você tem {tem} de {ticker}, então não dá para vender {qtd}."
        preco = _preco(_buscar(ticker))
        lucro = (preco - pos["preco_medio"]) * qtd
        pos["qtd"] -= qtd
        if pos["qtd"] == 0:
            del carteira["posicoes"][ticker]
        carteira["caixa"] += preco * qtd
        _registrar(carteira, "venda", ticker, qtd, preco, motivo, lucro)
        _salvar(carteira)
        resultado = "lucro" if lucro >= 0 else "prejuízo"
        return (f"Simulação: vendi {qtd} de {ticker} a {_reais(preco)} cada, com {resultado} de "
                f"{_reais(abs(lucro))}. Caixa agora: {_reais(carteira['caixa'])}.")
    except ErroBolsa as erro:
        return str(erro)


def _avaliar(carteira):
    """Valor atual das posições: (total, linhas, tickers sem cotação, que entram pelo preço de compra)."""
    total, linhas, falhas = 0.0, [], []
    for ticker, pos in carteira["posicoes"].items():
        custo = pos["qtd"] * pos["preco_medio"]
        try:
            preco = _preco(_buscar(ticker))
        except ErroBolsa:
            falhas.append(ticker)
            total += custo
            continue
        valor = preco * pos["qtd"]
        total += valor
        linhas.append((ticker, pos["qtd"], pos["preco_medio"], preco, valor - custo))
    return total, linhas, falhas


def ver_carteira() -> str:
    carteira = _carregar()
    if not carteira["posicoes"]:
        return f"Você ainda não tem ações na carteira simulada. Caixa: {_reais(carteira['caixa'])}."
    total, linhas, falhas = _avaliar(carteira)
    partes = [f"Caixa: {_reais(carteira['caixa'])}."]
    for ticker, qtd, medio, preco, resultado in linhas:
        partes.append(f"{ticker}: {qtd} ações, preço médio {_reais(medio)}, agora {_reais(preco)}, "
                      f"{'lucro' if resultado >= 0 else 'prejuízo'} de {_reais(abs(resultado))}.")
    if falhas:
        partes.append(f"Sem cotação agora para {', '.join(falhas)}; contei pelo preço de compra.")
    partes.append(f"Patrimônio total: {_reais(carteira['caixa'] + total)}.")
    return " ".join(partes)


def desempenho() -> str:
    carteira = _carregar()
    inicial = carteira.get("caixa_inicial", CAIXA_INICIAL)
    total, _, falhas = _avaliar(carteira)
    patrimonio = carteira["caixa"] + total
    variacao = (patrimonio - inicial) / inicial * 100
    vendas = [h for h in carteira["historico"] if h["tipo"] == "venda"]
    compras = len(carteira["historico"]) - len(vendas)

    partes = [f"Patrimônio simulado: {_reais(patrimonio)}, começando com {_reais(inicial)}. "
              f"Resultado: {'ganho' if variacao >= 0 else 'perda'} de {_pct(abs(variacao))}.",
              f"Você fez {compras} compras e {len(vendas)} vendas."]
    if vendas:
        acertos = sum(1 for v in vendas if v["lucro"] > 0)
        melhor = max(vendas, key=lambda v: v["lucro"])
        pior = min(vendas, key=lambda v: v["lucro"])
        realizado = sum(v["lucro"] for v in vendas)
        partes.append(f"Vendas com lucro: {acertos} de {len(vendas)}. Nas vendas, {_resultado(realizado)}. "
                      f"Melhor: {melhor['ativo']}, {_resultado(melhor['lucro'])}. "
                      f"Pior: {pior['ativo']}, {_resultado(pior['lucro'])}.")
    if falhas:
        partes.append(f"Sem cotação agora para {', '.join(falhas)}.")
    partes.append("Lembre que é simulação, sem custos e com dados atrasados, "
                  "e que resultado passado não garante o futuro.")
    return " ".join(partes)


def historico_operacoes() -> str:
    historico = _carregar()["historico"][-10:]
    if not historico:
        return "Ainda não há operações na simulação."
    linhas = []
    for h in historico:
        dia = f"{h['data'][8:10]}/{h['data'][5:7]}"
        linha = f"{dia}: {h['tipo']} de {h['qtd']} {h['ativo']} a {_reais(h['preco'])}"
        if h["tipo"] == "venda":
            linha += f", {'lucro' if h['lucro'] >= 0 else 'prejuízo'} de {_reais(abs(h['lucro']))}"
        if h.get("motivo"):
            linha += f". Motivo: {h['motivo']}"
        linhas.append(linha)
    return " | ".join(linhas)


# ---------------- Registro para o Llama ----------------

def _schema(nome, descricao, propriedades=None, obrigatorios=()):
    return {"type": "function", "function": {
        "name": nome, "description": descricao,
        "parameters": {"type": "object", "properties": propriedades or {},
                       "required": list(obrigatorios)}}}


_ATIVO = {"type": "string", "description": "Nome da empresa ou código na B3, ex.: Petrobras ou PETR4"}
_QTD = {"type": "integer", "description": "Quantidade de ações"}
_MOTIVO = {"type": "string", "description": "Motivo da operação, se o usuário disser (opcional)"}

FUNCOES = {
    "cotacao": cotacao,
    "comprar_simulado": comprar_simulado,
    "vender_simulado": vender_simulado,
    "ver_carteira": ver_carteira,
    "desempenho": desempenho,
    "historico_operacoes": historico_operacoes,
}

SCHEMAS = [
    _schema("cotacao", "Consulta o preço atual de uma ação da bolsa brasileira (B3).",
            {"ativo": _ATIVO}, ["ativo"]),
    _schema("comprar_simulado", "Compra ações na carteira SIMULADA (dinheiro fictício, não é real).",
            {"ativo": _ATIVO, "quantidade": _QTD, "motivo": _MOTIVO}, ["ativo", "quantidade"]),
    _schema("vender_simulado", "Vende ações da carteira SIMULADA (dinheiro fictício, não é real).",
            {"ativo": _ATIVO, "quantidade": _QTD, "motivo": _MOTIVO}, ["ativo", "quantidade"]),
    _schema("ver_carteira", "Mostra a carteira simulada: caixa, ações, lucro ou prejuízo de cada uma."),
    _schema("desempenho", "Mostra o desempenho da simulação: resultado total, vendas com lucro, melhor e pior."),
    _schema("historico_operacoes", "Lista as últimas operações simuladas, com os motivos anotados."),
]
