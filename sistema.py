"""
Fantasma - controle do computador: volume, desligar, reiniciar e bloquear a tela.

Volume: funciona no Windows (teclas de mídia, sem instalar nada), macOS e Linux.
Desligar, reiniciar e bloquear: só no Windows por enquanto.

SEGURANÇA: desligar e reiniciar não são imediatos. Eles agendam com contagem
(SEGUNDOS_DESLIGAR) e podem ser cancelados, caso o modelo chame a ferramenta por engano.
"""

import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"

SEGUNDOS_DESLIGAR = 30  # contagem antes de desligar/reiniciar
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

VK_MUDO, VK_VOLUME_MENOS, VK_VOLUME_MAIS = 0xAD, 0xAE, 0xAF  # teclas de mídia do Windows


def _executar(comando):
    return subprocess.run(comando, capture_output=True, text=True, errors="ignore",
                          creationflags=_SEM_JANELA)


def _percentual(valor, padrao):
    try:
        numero = int(float(valor))
    except (TypeError, ValueError):
        numero = padrao
    return max(0, min(100, numero))


def _tecla_midia(codigo, vezes=1):
    import ctypes
    usuario = ctypes.windll.user32
    for _ in range(vezes):
        usuario.keybd_event(codigo, 0, 0, 0)   # aperta
        usuario.keybd_event(codigo, 0, 2, 0)   # solta
        time.sleep(0.01)


def _mudar_volume(delta):
    """Muda o volume em `delta` pontos percentuais (positivo ou negativo)."""
    if WINDOWS:
        _tecla_midia(VK_VOLUME_MAIS if delta > 0 else VK_VOLUME_MENOS,
                     max(1, round(abs(delta) / 2)))  # cada toque muda ~2%
    elif MAC:
        _executar(["osascript", "-e",
                   f"set volume output volume ((output volume of (get volume settings)) + {delta})"])
    else:
        _executar(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{delta:+d}%"])


# ---------------- Ferramentas ----------------

def aumentar_volume(quanto=10) -> str:
    try:
        n = _percentual(quanto, 10) or 10
        _mudar_volume(n)
        return f"Volume aumentado em cerca de {n}%."
    except Exception as erro:
        return f"Não consegui mudar o volume: {erro}"


def diminuir_volume(quanto=10) -> str:
    try:
        n = _percentual(quanto, 10) or 10
        _mudar_volume(-n)
        return f"Volume diminuído em cerca de {n}%."
    except Exception as erro:
        return f"Não consegui mudar o volume: {erro}"


def definir_volume(percentual=50) -> str:
    try:
        n = _percentual(percentual, 50)
        if WINDOWS:
            _tecla_midia(VK_VOLUME_MENOS, 50)             # zera
            _tecla_midia(VK_VOLUME_MAIS, round(n / 2))    # sobe até o nível
        elif MAC:
            _executar(["osascript", "-e", f"set volume output volume {n}"])
        else:
            _executar(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{n}%"])
        return f"Volume ajustado para cerca de {n}%."
    except Exception as erro:
        return f"Não consegui mudar o volume: {erro}"


def silenciar_volume() -> str:
    try:
        if WINDOWS:
            _tecla_midia(VK_MUDO)
        elif MAC:
            _executar(["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"])
        else:
            _executar(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
        return "Alternei o mudo (se estava mudo, voltou o som; se não, silenciei)."
    except Exception as erro:
        return f"Não consegui alterar o mudo: {erro}"


def _agendar(opcao: str, nome: str) -> str:
    if not WINDOWS:
        return "Por enquanto isso só funciona no Windows."
    r = _executar(["shutdown", opcao, "/t", str(SEGUNDOS_DESLIGAR)])
    if r.returncode == 1190:
        return "Já existe um desligamento ou reinício agendado. O usuário pode pedir para cancelar."
    if r.returncode != 0:
        return f"Não consegui agendar: {r.stderr.strip()}"
    return (f"{nome} agendado para daqui a {SEGUNDOS_DESLIGAR} segundos. Avise o usuário "
            "e diga que ele pode pedir 'cancelar desligamento' para desfazer.")


def desligar_computador() -> str:
    return _agendar("/s", "Desligamento")


def reiniciar_computador() -> str:
    return _agendar("/r", "Reinício")


def cancelar_desligamento() -> str:
    if not WINDOWS:
        return "Por enquanto isso só funciona no Windows."
    r = _executar(["shutdown", "/a"])
    if r.returncode == 1116:
        return "Não havia nenhum desligamento agendado."
    if r.returncode != 0:
        return f"Não consegui cancelar: {r.stderr.strip()}"
    return "Desligamento cancelado."


def bloquear_tela() -> str:
    if not WINDOWS:
        return "Por enquanto isso só funciona no Windows."
    _executar(["rundll32.exe", "user32.dll,LockWorkStation"])
    return "Tela bloqueada."


# ---------------- Registro para o Llama ----------------

def _schema(nome, descricao, propriedades=None):
    return {"type": "function", "function": {
        "name": nome, "description": descricao,
        "parameters": {"type": "object", "properties": propriedades or {}}}}


_QUANTO = {"quanto": {"type": "integer", "description": "Quantos por cento (padrão 10)"}}

FUNCOES = {
    "aumentar_volume": aumentar_volume,
    "diminuir_volume": diminuir_volume,
    "definir_volume": definir_volume,
    "silenciar_volume": silenciar_volume,
    "desligar_computador": desligar_computador,
    "reiniciar_computador": reiniciar_computador,
    "cancelar_desligamento": cancelar_desligamento,
    "bloquear_tela": bloquear_tela,
}

SCHEMAS = [
    _schema("aumentar_volume", "Aumenta o volume do som do computador.", _QUANTO),
    _schema("diminuir_volume", "Diminui o volume do som do computador.", _QUANTO),
    _schema("definir_volume", "Ajusta o volume do computador para um nível exato.",
            {"percentual": {"type": "integer", "description": "Nível de 0 a 100"}}),
    _schema("silenciar_volume", "Silencia ou reativa o som do computador (mudo)."),
    _schema("desligar_computador", "Desliga o computador (com contagem de 30 segundos, cancelável). "
            "Só use se o usuário pedir explicitamente."),
    _schema("reiniciar_computador", "Reinicia o computador (com contagem de 30 segundos, cancelável). "
            "Só use se o usuário pedir explicitamente."),
    _schema("cancelar_desligamento", "Cancela um desligamento ou reinício agendado."),
    _schema("bloquear_tela", "Bloqueia a tela do computador."),
]
