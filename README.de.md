![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)

# SYR Connect - Home Assistant Integration

![Syr](custom_components/syr_connect/logo.png)

Dieses Custom Integration ermöglicht die Einbindung von SYR Connect Geräten in Home Assistant.

## Installation

### HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu "Integrationen"
3. Klicke die drei Punkte oben rechts
4. Wähle "Custom repositories"
5. Füge die Repository-URL hinzu
6. Wähle als Kategorie "Integration"
7. Klicke "Add"
8. Suche nach "SYR Connect" und installiere es
9. Starte Home Assistant neu

### Manuelle Installation

1. Kopiere den Ordner `syr_connect` in dein Verzeichnis `custom_components`
2. Starte Home Assistant neu

## Konfiguration

1. Gehe zu Einstellungen > Geräte & Dienste
2. Klicke auf "+ Integration hinzufügen"
3. Suche nach "SYR Connect"
4. Gib deine SYR Connect App-Zugangsdaten ein:
   - Benutzername
   - Passwort

## Funktionen

Die Integration erstellt automatisch Entitäten für alle SYR Connect Geräte in deinem Konto.

### Unterstützte Geräte

Diese Integration funktioniert mit SYR Enthärtungsanlagen, die im SYR Connect Cloud-Portal auftauchen.

Getestet und berichtet funktionierend:
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

Nicht getestet, sollte aber funktionieren:
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect
- SYR LEX 1500 Connect Einzel
- SYR LEX 1500 Connect Doppel
- SYR LEX 1500 Connect Pendel
- SYR LEX 1500 Connect Dreifach
- SYR IT 3000 Pendelanlage
- Andere SYR-Modelle mit Connect-Funktion oder nachgerüstetem Gateway

**Hinweis**: Wenn das Gerät in deinem SYR Connect Account sichtbar ist, wird die Integration es automatisch erkennen und Entitäten erstellen. Bei "ungetesteten Geräten" hilft es, Diagnose-Daten zu teilen, um unbekannte Werte zu identifizieren.

### Unterstützte Funktionalität

#### Sensoren
Die Integration bietet umfangreiche Überwachung, z. B.:

- Wasserhärte Ein-/Ausgang
- Restkapazität
- Gesamtkapazität
- Einheit der Wasserhärte
- Regenerationsstatus (aktiv/inaktiv)
- Anzahl der Regenerationen
- Regenerationsintervall und -zeit
- Salzbestand und -menge in Behältern
- Druck- und Durchflussüberwachung
- Betriebszustand und Alarmstatus

#### Binary Sensors
- Regeneration aktiv
- Betriebszustand
- Alarmstatus

#### Buttons (Aktionen)
- Sofort regenerieren (`setSIR`)
- Mehrfach regenerieren (`setSMR`)
- Gerät zurücksetzen (`setRST`)

### Bekannte Einschränkungen

- Cloud-Abhängigkeit: Die Integration benötigt eine aktive Internetverbindung und funktionierenden SYR Connect Cloud-Dienst
- Mindest-Updateintervall empfohlen: 60 Sekunden
- Meistens read-only: Nur Regenerationsaktionen sind möglich
- Pro Home Assistant-Instanz nur ein SYR Connect Account
- Keine lokale API: Kommunikation über Cloud-API

## Wie die Daten aktualisiert werden

Die Integration pollt die SYR Connect API in regelmäßigen Abständen (Standard: 60 Sekunden):

1. Login
2. Geräteerkennung
3. Statusaktualisierungen
4. Aktualisierung der Home Assistant Entitäten

Wenn ein Gerät offline ist, werden die Entitäten als `unavailable` markiert, bis ein erfolgreiches Update erfolgt.

## Anwendungsbeispiele
- Automatisierung: Salzwarnung, täglicher Regenerationsbericht, Alarmbenachrichtigung, Durchflussüberwachung, geplante Regenerationen (siehe original README für Beispiele)

## Konfigurationsoptionen

Scan-Intervall kann in den Integration-Optionen angepasst werden (Standard 60 Sekunden).

## Entfernen

1. Einstellungen > Geräte & Dienste
2. SYR Connect Integration auswählen
3. Menü (⋮) > Löschen

## Troubleshooting

- Diagnosedaten können heruntergeladen werden (sensible Daten werden automatisch unkenntlich gemacht)
- Verbindungs- und Authentifizierungsfehler: Zugangsdaten prüfen, App testen, Logs prüfen

## Abhängigkeiten

- `pycryptodomex==3.19.0`

## Lizenz

MIT License - siehe LICENSE Datei

## Danksagungen

- Basierend auf dem [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) Adapter von TA2k.
- Danke an das SYR IoT-Entwicklungsteam für Logos.
