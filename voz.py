"""
Fantasma - voz de saída com Piper (gratuito, local, português do Brasil).

Requisitos:  pip install piper-tts sounddevice numpy
A voz (pt_BR-faber-medium) é baixada automaticamente na primeira vez.
Se o Piper falhar, usa a voz do sistema (pyttsx3) como reserva.
"""

import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

PASTA_VOZES = Path(__file__).parent / "vozes"
VOZ = "pt_BR-cadu-medium"
URL_BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            "pt/pt_BR/cadu/medium/")

# Velocidade da fala: 1.0 = normal | maior = mais LENTO (ex.: 1.3) | menor = mais rápido
VELOCIDADE = 1.3

_voz_pronta = False
_cancelar = threading.Event()  # pedido de parada da fala atual
_motor_reserva = None
_opcao_velocidade = "?"  # descoberto automaticamente na primeira fala


def _python() -> str:
    """Com pythonw (sem terminal), usa o python.exe comum para rodar o Piper."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return sys.executable


def _baixar_voz():
    """Baixa os dois arquivos da voz, se ainda não existirem."""
    global _voz_pronta
    PASTA_VOZES.mkdir(exist_ok=True)
    for extensao in (".onnx", ".onnx.json"):
        destino = PASTA_VOZES / f"{VOZ}{extensao}"
        if destino.exists():
            continue
        print(f"[Voz] Baixando {destino.name} (só na primeira vez)...")
        temporario = destino.with_suffix(destino.suffix + ".tmp")
        urllib.request.urlretrieve(URL_BASE + VOZ + extensao, temporario)
        temporario.replace(destino)
    _voz_pronta = True


def _falar_piper(texto: str):
    if not _voz_pronta:
        _baixar_voz()

    modelo = PASTA_VOZES / f"{VOZ}.onnx"
    fd, saida = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        global _opcao_velocidade
        base = [_python(), "-m", "piper", "--model", str(modelo), "--output_file", saida]

        if VELOCIDADE == 1.0:
            opcoes = (None,)
        elif _opcao_velocidade != "?":
            opcoes = (_opcao_velocidade,)  # já descobrimos qual funciona
        else:
            opcoes = ("--length-scale", "--length_scale", None)

        for opcao in opcoes:
            comando = base + ([opcao, str(VELOCIDADE)] if opcao else [])
            # Força UTF-8: sem isso, no Windows o Piper pode ler os acentos errado
            ambiente = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            resultado = subprocess.run(comando, input=texto.encode("utf-8"),
                                       capture_output=True, env=ambiente,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            erro = resultado.stderr.decode("utf-8", "ignore")
            if resultado.returncode == 0:
                _opcao_velocidade = opcao
                break
            if opcao is not None and "unrecognized" in erro:
                continue  # esta versão do Piper usa outro nome de opção; tenta a próxima
            raise RuntimeError(erro[-300:])

        with wave.open(saida, "rb") as arquivo:
            taxa = arquivo.getframerate()
            canais = arquivo.getnchannels()
            audio = np.frombuffer(arquivo.readframes(arquivo.getnframes()), dtype=np.int16)
        if canais > 1:
            audio = audio.reshape(-1, canais)

        if _cancelar.is_set():  # parou durante a geração da voz
            return
        sd.play(audio, taxa)
        sd.wait()
    finally:
        try:
            os.remove(saida)
        except OSError:
            pass


def _falar_sistema(texto: str):
    """Voz de reserva: robótica, mas funciona offline sem nenhuma configuração."""
    global _motor_reserva
    if _motor_reserva is None:
        import pyttsx3
        _motor_reserva = pyttsx3.init()
        for v in _motor_reserva.getProperty("voices"):
            nome = f"{v.name} {v.id}".lower()
            if "brazil" in nome or "portugu" in nome or "pt-br" in nome or "pt_br" in nome:
                _motor_reserva.setProperty("voice", v.id)
                break
        _motor_reserva.setProperty("rate", 170)
    _motor_reserva.say(texto)
    _motor_reserva.runAndWait()


def parar():
    """Interrompe a fala atual, inclusive enquanto a voz ainda está sendo gerada."""
    _cancelar.set()
    sd.stop()
    if _motor_reserva is not None:
        try:
            _motor_reserva.stop()
        except Exception:
            pass


def falar(texto: str):
    _cancelar.clear()
    # Limpa símbolos que não devem ser lidos em voz alta
    for simbolo in ("*", "#", "`", "_"):
        texto = texto.replace(simbolo, "")
    texto = " ".join(texto.split())
    if not texto:
        return
    try:
        _falar_piper(texto)
    except Exception as erro:
        print(f"[Voz] Piper indisponível ({erro}). Usando a voz do sistema.")
        _falar_sistema(texto)


if __name__ == "__main__":
    falar("Olá! Não há problema nenhum. Ação, coração, avó, você, também, "
          "atenção, pôr do sol e Arenápolis, em Mato Grosso.")
