# Home Assistant Brand Images Generator

Dieses Skript erstellt alle benötigten PNG-Logos und Icons für die Home Assistant Integration gemäß den Vorgaben des [brands repositories](https://github.com/home-assistant/brands).

## Voraussetzungen

- Python 3.7 oder neuer
- Pillow-Bibliothek (für Bildverarbeitung)
- Quelldatei: Das Logo muss als PNG im Ordner `icons` liegen, z.B. `syr_logo_cmyk.original.png`

## Installation

1. Pillow installieren:

```bash
pip install Pillow
```

2. Logo-Datei in den Ordner `icons` kopieren und ggf. den Dateinamen im Skript (`generate_brand_images.py`) anpassen.

## Ausführung

Im Ordner `icons` das Skript ausführen:

```bash
python generate_brand_images.py
```

Die generierten Dateien werden im selben Ordner abgelegt:
- icon.png
- icon@2x.png
- logo.png
- logo@2x.png
- dark_icon.png
- dark_icon@2x.png
- dark_logo.png
- dark_logo@2x.png

## Hinweise

- Die Bildgrößen und Dateinamen entsprechen den Home Assistant Vorgaben.
- Für dunkle Varianten wird ein halbtransparenter schwarzer Overlay verwendet.
- Das Skript kann bei Bedarf angepasst werden (z.B. für andere Dateinamen oder Größen).

## Fehlerbehebung

- Bei `FileNotFoundError`: Prüfe, ob der Dateiname in `SOURCE_PATH` korrekt ist und die Datei im icons-Ordner liegt.
- Bei Pillow-Importfehler: Stelle sicher, dass Pillow im richtigen Python-Umfeld installiert ist.

---

Fragen oder Probleme? Siehe [brands repository](https://github.com/home-assistant/brands) für weitere Details zu den Anforderungen.