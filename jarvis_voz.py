"""
Fantasma - conversa por voz com palavra de ativação ("ei Fantasma"),
100% local e gratuita.

Como funciona: um Whisper leve (modelo "base") escuta o ambiente. Quando detecta
uma fala, transcreve e confere se o nome "Fantasma" aparece no começo da frase.
Se aparecer, o assistente acorda. Se você já disse o comando junto
("Ei Fantasma, que horas são?"), ele responde direto, sem bipe.

Requisitos:
  pip install faster-whisper sounddevice numpy piper-tts pyttsx3 -U ollama
  (Linux: sudo apt install espeak-ng libportaudio2)
  Deixe na mesma pasta: jarvis.py, ferramentas.py e voz.py.
"""

import difflib
import re
import threading
from collections import deque

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from jarvis import conversar  # cérebro + ferramentas
from voz import falar, parar as parar_fala  # voz do Fantasma (Piper)
from ferramentas import CIDADES_CONHECIDAS, _sem_acento

TEM_ATIVACAO = True  # (usado pelo jarvis_web.py)

# ---------------- Configurações ----------------
NOME = "fantasma"          # palavra que acorda o assistente (sem acento, minúscula)
TAXA_WHISPER = 16000       # o Whisper espera áudio em 16 kHz
SEGUNDOS = 5               # tempo de gravação do comando depois da ativação
MODELO_WHISPER = "small"   # entende os comandos; use "base" se o PC for fraco
MODELO_ATIVACAO = "base"   # leve: só procura o nome (use "tiny" se o PC for muito fraco)
MICROFONE = None           # número do microfone (None = padrão; veja teste_microfone.py)

INTERROMPER_POR_VOZ = True # dizer "ei Fantasma" no meio da fala dele para interrompê-lo
NIVEL_MINIMO = 0.008        # volume mínimo para considerar que há fala (suba se o ambiente for barulhento)
GANHO_MICROFONE = 3.0      # multiplica o volume captado (ex.: 3.0 se sua voz sai baixa; rode calibrar_microfone.py)
SENSIBILIDADE_VOZ = 3.0    # fala = volume acima do ruído de fundo × este valor (menor = mais sensível)
DEPURAR = False            # True mostra o que ele ouviu, para calibrar

PALAVRAS_SAIR = ("sair", "encerrar", "tchau", "até logo", "desligar")
# -------------------------------------------------

BLOCOS_SILENCIO = 7   # 0,7 s de silêncio encerra a frase
BLOCOS_MAX = 100      # frase de no máximo 10 s
BLOCOS_MIN_VOZ = 4    # ignora ruídos com menos de 0,4 s

PROMPT_VOCABULARIO = ("Conversa em português do Brasil com o assistente Fantasma. "
                      "Cidades: " + ", ".join(CIDADES_CONHECIDAS) + ".")
PROMPT_ATIVACAO = "Conversa em português do Brasil."

print("Carregando modelo de voz (pode demorar na primeira vez)...")
whisper = WhisperModel(MODELO_WHISPER, device="cpu", compute_type="int8")


def _transcrever(modelo, audio, beam, prompt):
    segmentos, _ = modelo.transcribe(audio, language="pt", vad_filter=False,
                                     beam_size=beam, initial_prompt=prompt)
    return " ".join(s.text.strip() for s in segmentos).strip()


def _achar_nome(texto):
    """Se o nome aparece no começo da frase, devolve o que veio depois ('' se nada). Senão, None."""
    for i, m in enumerate(re.finditer(r"\w+", texto)):
        if i > 2:
            break
        if difflib.SequenceMatcher(None, _sem_acento(m.group()), NOME).ratio() >= 0.95:
            return texto[m.end():].strip(" ,.;:!?-…")
    return None


class Detector:
    """Procura o nome do assistente numa frase gravada."""

    def __init__(self):
        self.rapido = WhisperModel(MODELO_ATIVACAO, device="cpu", compute_type="int8")

    def procurar(self, audio):
        pico = float(np.abs(audio).max())
        if 0 < pico < 0.5:  # voz baixa: amplifica antes de transcrever
            audio = (audio * (0.6 / pico)).astype("float32")
        texto = _transcrever(self.rapido, audio, 1, PROMPT_ATIVACAO)
        if DEPURAR:
            print(f"   [ouvi: {texto!r}]")
        comando = _achar_nome(texto)
        if comando is None:
            return None
        if len(comando.split()) >= 2:  # já veio um comando: refaz com o modelo mais preciso
            preciso = _achar_nome(_transcrever(whisper, audio, 5, PROMPT_VOCABULARIO))
            if preciso is not None:
                comando = preciso
        return comando


def carregar_ativacao():
    """Carrega o detector do nome. Retorna None se falhar."""
    try:
        return Detector()
    except Exception as erro:
        print(f"[Ativação] Não consegui carregar o modelo de ativação: {erro}")
        return None


def esperar_ativacao(detector, continuar=lambda: True):
    """
    Escuta o microfone até ouvir o nome do assistente.
    Retorna o comando dito junto ('' se foi só o nome) ou None se `continuar()` virou falso antes.
    """
    taxa = TAXA_WHISPER
    try:
        sd.check_input_settings(device=MICROFONE, samplerate=taxa, channels=1)
    except Exception:
        taxa = int(sd.query_devices(MICROFONE, "input")["default_samplerate"])
    bloco = int(taxa * 0.1)  # 100 ms por vez

    pre = deque(maxlen=3)    # guarda o início da fala, antes de ela ser detectada
    trecho, falando, silencio, ruido = [], False, 0, 0.005

    with sd.InputStream(samplerate=taxa, channels=1, dtype="float32",
                        blocksize=bloco, device=MICROFONE) as fluxo:
        while continuar():
            dados, _ = fluxo.read(bloco)
            quadro = dados[:, 0]
            if taxa != TAXA_WHISPER:
                quadro = np.interp(np.linspace(0, len(quadro) - 1, 1600),
                                   np.arange(len(quadro)), quadro).astype("float32")

            quadro = np.clip(quadro * GANHO_MICROFONE, -1.0, 1.0)
            nivel = float(np.sqrt(np.mean(quadro ** 2)))
            limiar = max(NIVEL_MINIMO, ruido * SENSIBILIDADE_VOZ)

            if not falando:
                ruido = 0.95 * ruido + 0.05 * nivel  # aprende o barulho de fundo
                if nivel > limiar:
                    falando, trecho, silencio = True, list(pre) + [quadro], 0
                else:
                    pre.append(quadro)
                continue

            trecho.append(quadro)
            silencio = silencio + 1 if nivel < limiar else 0
            if silencio >= BLOCOS_SILENCIO or len(trecho) >= BLOCOS_MAX:
                voz = len(trecho) - silencio
                audio = np.concatenate(trecho)
                trecho, falando, silencio = [], False, 0
                pre.clear()
                if voz < BLOCOS_MIN_VOZ:
                    continue  # barulho curto
                comando = detector.procurar(audio)
                if comando is not None:
                    return comando
    return None


def falar_interrompivel(texto, detector):
    """
    Fala a resposta. Se você disser "ei Fantasma" no meio, ele para.
    Retorna None se falou até o fim, ou o comando dito ao interromper ('' se foi só o nome).
    """
    if detector is None or not INTERROMPER_POR_VOZ or NOME in _sem_acento(texto):
        falar(texto)
        return None
    fala = threading.Thread(target=falar, args=(texto,), daemon=True)
    fala.start()
    comando = esperar_ativacao(detector, continuar=fala.is_alive)
    if comando is not None:
        parar_fala()
    fala.join()
    return comando


def bipe():
    """Sinal sonoro curto avisando que o Fantasma está ouvindo."""
    t = np.linspace(0, 0.15, int(44100 * 0.15), endpoint=False)
    tom = (0.3 * np.sin(2 * np.pi * 880 * t)).astype("float32")
    sd.play(tom, 44100)
    sd.wait()


def ouvir() -> str:
    """Grava alguns segundos do microfone e transcreve para texto."""
    info = sd.query_devices(MICROFONE, "input")
    taxa = int(info["default_samplerate"])
    print(f"🎙️  Pode falar ({SEGUNDOS}s)...")

    gravacao = sd.rec(int(SEGUNDOS * taxa), samplerate=taxa, channels=1,
                      dtype="float32", device=MICROFONE)
    sd.wait()
    audio = gravacao.flatten()

    pico = float(np.abs(audio).max())
    if pico < 0.01:
        print("   ⚠️  Quase silêncio. Rode teste_microfone.py para conferir o microfone.")
        return ""

    if taxa != TAXA_WHISPER:
        n = int(len(audio) * TAXA_WHISPER / taxa)
        audio = np.interp(np.linspace(0, len(audio) - 1, n),
                          np.arange(len(audio)), audio).astype("float32")

    if pico < 0.3:  # volume baixo: amplifica
        audio = np.clip(audio * (0.5 / pico), -1.0, 1.0).astype("float32")

    return _transcrever(whisper, audio, 5, PROMPT_VOCABULARIO)


def main():
    ativacao = carregar_ativacao()
    if ativacao is None:
        print("Modo manual: aperte Enter para falar.")

    falar("Fantasma online.")
    pendente = None  # comando já dito junto com o nome (ou ao interromper)
    try:
        while True:
            if ativacao:
                if pendente is None:
                    print("\n👂 Aguardando você dizer 'ei Fantasma'... (Ctrl+C para sair)")
                    pendente = esperar_ativacao(ativacao)
                comando, pendente = pendente, None
                if comando:
                    texto = comando
                else:
                    bipe()
                    texto = ouvir()
            else:
                input("\n[Enter] para falar (Ctrl+C para sair): ")
                texto = ouvir()

            if not texto:
                print("Não ouvi nada.")
                continue

            print(f"Você: {texto}")
            if texto.lower().strip(" .!?") in PALAVRAS_SAIR:
                falar("Até logo!")
                break

            try:
                resposta = conversar(texto)
            except Exception as erro:
                print(f"[Erro] Verifique se o Ollama está rodando.\n{erro}")
                continue

            print(f"Fantasma: {resposta}")
            pendente = falar_interrompivel(resposta, ativacao)
    except KeyboardInterrupt:
        print("\nEncerrando o Fantasma.")


if __name__ == "__main__":
    main()
