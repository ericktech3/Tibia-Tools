"""Procura erros Python reais no logcat do teste de emulador.

Ignora o aviso inofensivo do Kivy ao copiar seus ícones para .kivy/icon
(o próprio Kivy trata esse erro e o app continua normalmente).
"""
import re
import sys

HARMLESS = ("kivy-icon", ".kivy/icon")

text = open(sys.argv[1] if len(sys.argv) > 1 else "logcat.txt", errors="ignore").read()
parts = re.split(r"Traceback \(most recent call last\):", text)
real = []
for block in parts[1:]:
    lines = block.splitlines()[:40]
    chunk = "\n".join(lines)
    if any(h in chunk for h in HARMLESS):
        continue
    real.append(chunk)

if real:
    for chunk in real:
        print("Traceback (most recent call last):")
        print(chunk)
        print("-" * 60)
    print(f"ERRO: {len(real)} erro(s) Python encontrado(s)")
    sys.exit(1)
print(f"OK: app aberto e sem erro Python ({len(parts) - 1} aviso(s) inofensivo(s) ignorado(s))")
