"""
Teste de microfone do Fantasma: mostra os microfones, mede o volume
e tenta transcrever o que você falou.

Uso: python teste_microfone.py
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

print("\n=== Microfones disponíveis ===")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        print(f"[{i}] {d['name']}")
padrao = sd.default.device[0]
print(f"\nMicrofone padrão do sistema: [{padrao}]")

escolha = input("Número do microfone para testar (Enter = padrão): ").strip()
dispositivo = int(escolha) if escolha else None

info = sd.query_devices(dispositivo, "input")
taxa = int(info["default_samplerate"])
print(f"\nUsando: {info['name']} ({taxa} Hz)")
input("Aperte Enter e fale uma frase por 5 segundos...")

gravacao = sd.rec(int(5 * taxa), samplerate=taxa, channels=1, dtype="float32", device=dispositivo)
sd.wait()
audio = gravacao.flatten()

pico = float(np.abs(audio).max())
print(f"\nNível máximo captado: {pico:.3f}")
if pico < 0.01:
    print("❌ Quase silêncio: microfone errado, mudo, ou sem permissão do sistema.")
elif pico < 0.05:
    print("⚠️  Volume muito baixo: aumente o ganho do microfone nas configurações de som.")
else:
    print("✅ O microfone está captando bem.")

if taxa != 16000:
    n = int(len(audio) * 16000 / taxa)
    audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype("float32")

print("\nTranscrevendo...")
whisper = WhisperModel("small", device="cpu", compute_type="int8")
segmentos, _ = whisper.transcribe(audio, language="pt", vad_filter=False)
texto = " ".join(s.text.strip() for s in segmentos).strip()
print(f"Ele entendeu: '{texto}'" if texto else "Não entendeu nada.")
