"""
Fantasma - calibração do microfone.

Mede o ruído do ambiente e o volume da sua voz normal, e sugere os valores de
NIVEL_MINIMO e GANHO_MICROFONE para colocar no topo do jarvis_voz.py.

Uso: python calibrar_microfone.py
"""

import numpy as np
import sounddevice as sd

MICROFONE = None  # use o mesmo número do jarvis_voz.py (None = padrão)


def gravar(segundos):
    taxa = int(sd.query_devices(MICROFONE, "input")["default_samplerate"])
    audio = sd.rec(int(segundos * taxa), samplerate=taxa, channels=1, dtype="float32", device=MICROFONE)
    sd.wait()
    return audio[:, 0], taxa


def niveis(audio, taxa):
    """Volume (RMS) de cada trecho de 100 ms."""
    n = int(taxa * 0.1)
    return np.array([np.sqrt(np.mean(audio[i:i + n] ** 2)) for i in range(0, len(audio) - n, n)])


def sugerir(ruido, fala):
    """Valores sugeridos a partir do ruído de fundo e do volume da fala (RMS)."""
    ganho = float(np.clip(0.08 / max(fala, 1e-6), 1.0, 8.0))
    minimo_bruto = max(0.002, min(np.sqrt(ruido * fala), fala * 0.5))
    # O Fantasma aplica o ganho ANTES de comparar com NIVEL_MINIMO, então o valor vai na escala amplificada
    return round(float(minimo_bruto * ganho), 4), round(ganho, 1)


def main():
    info = sd.query_devices(MICROFONE, "input")
    print(f"Microfone: {info['name']}\n")

    input("1) Fique em SILÊNCIO. Aperte Enter e aguarde 3 segundos...")
    audio, taxa = gravar(3)
    ruido = float(np.median(niveis(audio, taxa)))

    input("\n2) Aperte Enter e diga 'Ei Fantasma' 3 vezes, em volume NORMAL (como falaria no dia a dia)...")
    audio, taxa = gravar(6)
    n = niveis(audio, taxa)
    fala = float(np.percentile(n, 90))

    print(f"\nRuído de fundo: {ruido:.4f} | Sua voz: {fala:.4f} | Proporção: {fala / max(ruido, 1e-6):.1f}x")
    if fala < 0.003:
        print("❌ Quase não captei sua voz. Verifique o microfone (teste_microfone.py) e o volume de entrada do Windows.")
        return
    if fala / max(ruido, 1e-6) < 3:
        print("⚠️  Sua voz está muito perto do ruído. Aproxime o microfone, ou aumente o volume de entrada "
              "(Windows: Configurações > Sistema > Som > Entrada).")

    nivel_minimo, ganho = sugerir(ruido, fala)
    print("\nColoque no topo do jarvis_voz.py:")
    print(f"  NIVEL_MINIMO = {nivel_minimo}")
    print(f"  GANHO_MICROFONE = {ganho}")


if __name__ == "__main__":
    main()
