"""
Fantasma - diagnóstico: descobre por que ele não ouve ou não responde.

Uso:  python diagnostico.py
Antes, feche o Fantasma (botão Desligar na página), para o microfone ficar livre.
"""

import sys
import time


def titulo(texto):
    print(f"\n=== {texto}")


def ok(texto):
    print(f"  ✅ {texto}")


def falha(texto):
    print(f"  ❌ {texto}")


titulo("1) Python e bibliotecas")
print("  Python", sys.version.split()[0])
for nome in ("numpy", "sounddevice", "faster_whisper", "ollama", "piper"):
    try:
        modulo = __import__(nome)
        ok(f"{nome} {getattr(modulo, '__version__', '')}".strip())
    except Exception as erro:
        falha(f"{nome}: {erro}")

titulo("2) Ollama")
try:
    import jarvis
    import ollama
    inicio = time.time()
    resposta = ollama.chat(model=jarvis.MODELO, messages=[{"role": "user", "content": "Responda só: ok"}])
    ok(f"o modelo {jarvis.MODELO} respondeu em {time.time() - inicio:.1f} s: {resposta['message']['content'][:40]!r}")
except Exception as erro:
    falha(f"Ollama não respondeu: {erro}")
    print("     -> abra o aplicativo Ollama e confira o modelo com:  ollama list")

titulo("3) Ferramentas")
try:
    import ferramentas
    invalidas = [i for i, s in enumerate(ferramentas.SCHEMAS)
                 if not (isinstance(s, dict) and s.get("type") == "function" and "function" in s)]
    if invalidas:
        falha(f"{len(invalidas)} definições inválidas em SCHEMAS (posições {invalidas}). "
              "É isso que faz o Ollama recusar todas as perguntas.")
    else:
        ok(f"{len(ferramentas.SCHEMAS)} ferramentas com definição válida")
        ollama.chat(model=jarvis.MODELO, messages=[{"role": "user", "content": "que horas são?"}],
                    tools=ferramentas.SCHEMAS)
        ok("o Ollama aceitou as ferramentas")
except Exception as erro:
    falha(f"problema com as ferramentas: {erro}")

titulo("4) Voz do Fantasma")
try:
    import voz
    print("  (se aparecer '[Voz] Piper indisponível', o motivo vem na mesma linha)")
    voz.falar("Teste de voz. Você está me ouvindo?")
    ok("terminou de falar. Se você ouviu a voz, está tudo certo.")
except Exception as erro:
    falha(f"voz: {erro}")

titulo("5) Microfone e palavra de ativação (30 segundos)")
try:
    import jarvis_voz as jv

    jv.DEPURAR = True
    detector = jv.Detector()
    print("  Diga 'Ei Fantasma' algumas vezes e depois uma frase qualquer.")
    print("  Cada fala detectada aparece abaixo com o que o Whisper entendeu.\n")

    fim, ultimo = time.time() + 30, [0.0]

    def mostrar_nivel(nivel, limiar, falando):
        if time.time() - ultimo[0] > 0.4:
            ultimo[0] = time.time()
            barra = "█" * min(30, int(nivel * 150))
            estado = "FALANDO" if falando else "       "
            print(f"\r   volume {nivel:.3f} (limite {limiar:.3f}) {estado} {barra:<30}", end="", flush=True)

    resultado = jv.esperar_ativacao(detector, continuar=lambda: time.time() < fim, ao_nivel=mostrar_nivel)
    print()
    if resultado is None:
        falha("Em 30 segundos não reconheci o nome 'Fantasma'.")
        print("     -> Se o volume nunca passou do limite quando você falou: aumente GANHO_MICROFONE ou "
              "rode calibrar_microfone.py.")
        print("     -> Se aparece 'fala detectada' mas o [ouvi: ...] não tem 'Fantasma': "
              "o Whisper está entendendo outra palavra (diga qual).")
    else:
        ok(f"Reconheci o nome! Comando dito junto: {resultado!r}")
except Exception as erro:
    falha(f"microfone/ativação: {erro}")

print("\nFim do diagnóstico. Me envie tudo o que apareceu acima.")
