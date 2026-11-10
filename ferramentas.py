"""
Fantasma - Etapa 3: ferramentas (100% gratuitas, sem chave de API).

Cada ferramenta é uma função Python comum + uma descrição (schema) que
o Llama usa para decidir quando chamá-la.
"""

import difflib
import json
import unicodedata
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path  # <--- ADICIONADO

# Define a pasta do projeto para evitar o erro 'PASTA is not defined'
PASTA = Path(__file__).parent

# Cidade usada quando você não disser qual. Troque pela sua.
CIDADE_PADRAO = "Nortelândia, MT"

# Cidades que o Fantasma deve reconhecer bem (edite à vontade, mantenha até ~40 nomes).
# Elas ajudam o Whisper a ouvir certo e corrigem nomes parecidos.
CIDADES_CONHECIDAS = [
    "Arenápolis", "Diamantino", "Nobres", "Alto Paraguai", "Nortelândia",
    "Rosário Oeste", "Cuiabá", "Várzea Grande", "Rondonópolis", "Sinop",
    "Sorriso", "Tangará da Serra", "Lucas do Rio Verde", "Nova Mutum",
    "Primavera do Leste", "Barra do Garças", "Cáceres", "Campo Verde",
    "Pontes e Lacerda", "Juína", "Alta Floresta", "Campo Novo do Parecis",
    "Sapezal", "Brasnorte", "São Paulo", "Rio de Janeiro", "Brasília",
    "Goiânia", "Campo Grande", "Belo Horizonte", "Curitiba", "Porto Alegre",
    "Salvador", "Fortaleza", "Manaus",
]

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Sites que o Fantasma tem permissão de abrir (lista segura).
SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
}

CODIGOS_CLIMA = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado",
    3: "nublado", 45: "neblina", 48: "neblina com geada",
    51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    61: "chuva fraca", 63: "chuva moderada", 65: "chuva forte",
    80: "pancadas de chuva fracas", 81: "pancadas de chuva",
    82: "pancadas de chuva fortes", 95: "trovoada",
    96: "trovoada com granizo", 99: "trovoada com granizo forte",
}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto)
    return "".join(c for c in base if unicodedata.category(c) != "Mn").lower().strip()


def _corrigir_cidade(nome: str) -> str:
    """Corrige nomes mal transcritos comparando com a lista de cidades conhecidas."""
    alvo = _sem_acento(nome.split(",")[0])
    mapa = {_sem_acento(c): c for c in CIDADES_CONHECIDAS}
    for chave, original in mapa.items():       # a cidade aparece dentro do texto
        if chave in alvo:
            return original
    parecido = difflib.get_close_matches(alvo, list(mapa), n=1, cutoff=0.75)
    return mapa[parecido[0]] if parecido else nome


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


# ---------------- Ferramentas ----------------

def hora_atual() -> str:
    agora = datetime.now()
    return (f"{DIAS[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]} "
            f"de {agora.year}, {agora:%H:%M}")


def clima(cidade: str = CIDADE_PADRAO) -> str:
    try:
        cidade = _corrigir_cidade(cidade)
        busca = urllib.parse.urlencode({"name": cidade, "count": 10, "language": "pt"})
        geo = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?{busca}")
        resultados = geo.get("results") or []
        if not resultados:
            return f"Não encontrei a cidade {cidade}."
        # Prefere a cidade brasileira, se houver mais de uma com o mesmo nome
        local = next((r for r in resultados if r.get("country_code") == "BR"), resultados[0])

        params = urllib.parse.urlencode({
            "latitude": local["latitude"],
            "longitude": local["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        atual = _get_json(f"https://api.open-meteo.com/v1/forecast?{params}")["current"]

        descricao = CODIGOS_CLIMA.get(atual["weather_code"], "condição não identificada")
        return (f"Clima agora em {local['name']} ({local.get('admin1', '')}): {descricao}, "
                f"{atual['temperature_2m']}°C, sensação de {atual['apparent_temperature']}°C, "
                f"umidade {atual['relative_humidity_2m']}%, "
                f"vento {atual['wind_speed_10m']} km/h, "
                f"chuva {atual['precipitation']} mm.")
    except Exception as erro:
        return f"Não consegui consultar o clima (verifique a internet): {erro}"


def abrir_site(site: str) -> str:
    chave = site.strip().lower()
    if chave not in SITES:
        return f"Não tenho permissão para abrir '{site}'. Disponíveis: {', '.join(SITES)}."
    webbrowser.open(SITES[chave])
    return f"Abri o {chave} no navegador."


def tocar_musica(busca: str) -> str:
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(busca)
    webbrowser.open(url)
    return f"Abri a busca por '{busca}' no YouTube."

MEMORIA_ARQUIVO = PASTA / "memoria_usuario.json"

def guardar_memoria(chave: str, valor: str) -> str:
    """Guarda uma informação, preferência ou fato sobre o usuário na memória de longo prazo."""
    memoria = {}
    if MEMORIA_ARQUIVO.exists():
        try:
            memoria = json.loads(MEMORIA_ARQUIVO.read_text(encoding="utf-8"))
        except Exception:
            pass
    memoria[chave] = valor
    MEMORIA_ARQUIVO.write_text(json.dumps(memoria, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Lembrei-me disso! Registrei que {chave} é {valor}."

def ler_memorias() -> str:
    """Mostra todas as informações e preferências guardadas sobre o usuário."""
    if not MEMORIA_ARQUIVO.exists():
        return "Ainda não tenho nenhuma memória guardada sobre você."
    try:
        memoria = json.loads(MEMORIA_ARQUIVO.read_text(encoding="utf-8"))
        if not memoria:
            return "Ainda não tenho memórias guardadas."
        return " | ".join([f"{k}: {v}" for k, v in memoria.items()])
    except Exception:
        return "Erro ao ler as memórias."

def esquecer_memoria(chave: str) -> str:
    """Apaga uma informação da memória do usuário."""
    if not MEMORIA_ARQUIVO.exists():
        return "Não há memórias guardadas."
    memoria = json.loads(MEMORIA_ARQUIVO.read_text(encoding="utf-8"))
    chave_limpa = _sem_acento(chave)
    encontrada = next((k for k in memoria if _sem_acento(k) == chave_limpa), None)
    if encontrada:
        del memoria[encontrada]
        MEMORIA_ARQUIVO.write_text(json.dumps(memoria, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"Pronto, apaguei a memória sobre '{encontrada}'."
    return f"Não encontrei nenhuma memória com o nome '{chave}'."

# ---------------- Registro para o Llama ----------------

FUNCOES = {
    "hora_atual": hora_atual,
    "clima": clima,
    "abrir_site": abrir_site,
    "tocar_musica": tocar_musica,
    "guardar_memoria": guardar_memoria,
    "ler_memorias": ler_memorias,
    "esquecer_memoria": esquecer_memoria,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "guardar_memoria",
            "description": "Guarda uma informação, preferência ou fato sobre o usuário na memória de longo prazo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chave": {"type": "string", "description": "O que é, ex.: 'time_futebol' ou 'cor_favorita'"},
                    "valor": {"type": "string", "description": "O valor da informação, ex.: 'Flamengo' ou 'Azul'"},
                },
                "required": ["chave", "valor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_memorias",
            "description": "Lista todas as informações que você lembra sobre o usuário.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "esquecer_memoria",
            "description": "Apaga uma informação da memória do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chave": {"type": "string", "description": "Nome da chave a ser apagada"},
                },
                "required": ["chave"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hora_atual",
            "description": "Retorna a data, o dia da semana e a hora atuais.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clima",
            "description": "Consulta o clima atual (temperatura, chuva, vento) de uma cidade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cidade": {"type": "string",
                               "description": "Nome da cidade, por exemplo: Cuiabá"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_site",
            "description": "Abre um site no navegador do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {"type": "string",
                             "description": "Um de: " + ", ".join(SITES)},
                },
                "required": ["site"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tocar_musica",
            "description": "Procura uma música ou artista no YouTube para tocar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "busca": {"type": "string",
                              "description": "Nome da música ou artista"},
                },
                "required": ["busca"],
            },
        },
    },
]


# ---- Controle do computador (volume, desligar, reiniciar, bloquear) ----
from sistema import FUNCOES as _FUNCOES_SISTEMA, SCHEMAS as _SCHEMAS_SISTEMA

FUNCOES.update(_FUNCOES_SISTEMA)
SCHEMAS.extend(_SCHEMAS_SISTEMA)


# ---- Bolsa de valores: cotações e carteira simulada ----
from bolsa import FUNCOES as _FUNCOES_BOLSA, SCHEMAS as _SCHEMAS_BOLSA

FUNCOES.update(_FUNCOES_BOLSA)
SCHEMAS.extend(_SCHEMAS_BOLSA)
