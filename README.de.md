[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

# SYR Connect – Home Assistant Integration

![Syr](custom_components/syr_connect/logo.png)

Dieses Custom-Integration ermöglicht die Steuerung von SYR Connect-Geräten über Home Assistant.

## Installation

### HACS (empfohlen)

1. Öffne HACS in Home Assistant
2. Gehe zu „Integrationen“
3. Suche nach „SYR Connect“
4. Klicke auf „Installieren“
5. Starte Home Assistant neu

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

Diese Integration funktioniert mit SYR-Wasserenthärtern, die im SYR Connect-Cloud-Portal (über die SYR Connect App) sichtbar sind.

Getestet und gemeldet funktionierend:
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

Nicht getestet, sollte aber funktionieren (bitte melden):
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect
- SYR LEX 1500 Connect Einzel
- SYR LEX 1500 Connect Doppel
- SYR LEX 1500 Connect Pendel
- SYR LEX 1500 Connect Dreifach
- SYR IT 3000 Pendelanlage
- Andere SYR-Modelle mit Connect-Funktion oder nachgerüstetem Gateway

Auch Leckage-Erkennungsgeräte sind interessant, können aber zusätzlichen Aufwand erfordern:
- TRIO DFR/LS Connect 2425
- SafeTech Connect
- SafeTech plus Connect
- SafeFloor Connect

**Hinweis**: Wenn ein Gerät in deinem SYR Connect-Konto sichtbar ist, wird die Integration es automatisch entdecken und die Entitäten erstellen. Wenn du ein „ungetestetes Gerät“ besitzt, hilft es, diagnostische Daten zu teilen, damit unbekannte Werte analysiert und die Liste getesteter Geräte erweitert werden kann.

### Unterstützte Funktionen

#### Sensoren
Die Integration bietet umfangreiche Überwachung deines Wasserenthärters:

**Wasserqualität & Kapazität**
- Überwachung Ein-/Ausgangswasserhärte
- Verbleibende Kapazität
- Gesamtvolumen
- Anzeige der Einheit der Wasserhärte

**Regenerationsinformationen**
- Regenerationsstatus
- Anzahl durchgeführter Regenerationen
- Einstellung des Regenerationsintervalls
- Regenerationszeitplan

**Salzverwaltung**
- Salzmenge in Behältern (1–3)
- Salzvorrat
- Geschätzte Vorratsdauer

**Systemüberwachung**
- Wasserdruck
- Durchflussrate (aktuell)
- Durchflusszähler (Gesamtverbrauch)
- Alarmstatus

**Geräteinformationen** (standardmäßig deaktiviert, in der Diagnostik-Kategorie)
- Seriennummer
- Firmware-Version und Modell
- Gerätetyp und Hersteller
- Netzwerk-Informationen (IP, MAC, Gateway)

#### Binärsensoren
- Regeneration aktiv

#### Buttons (Aktionen)
- **Sofort regenerieren (setSIR)**: Sofortige Regeneration starten

### Bekannte Einschränkungen

- **Cloud-Abhängigkeit**: Diese Integration benötigt eine aktive Internetverbindung und den funktionierenden SYR Connect-Cloud-Dienst
- **Update-Intervall**: Empfohlenes Minimum ist 60 Sekunden, um API-Rate-Limits zu vermeiden
- **Read-Only Daten**: Die meisten Sensoren sind schreibgeschützt; nur Regenerationsaktionen können ausgelöst werden
- **Ein Konto pro Instanz**: Jede Home Assistant-Instanz kann nur mit einem SYR Connect-Konto verbunden werden
- **Keine lokale API**: Die Integration nutzt die Cloud-API; keine lokale Netzwerkkommunikation verfügbar

## Wie Daten aktualisiert werden

Die Integration pollt die SYR Connect-Cloud API in regelmäßigen Abständen (Standard: 60 Sekunden):

1. **Login**: Authentifiziert sich bei der SYR Connect API mit deinen Zugangsdaten
2. **Geräte-Erkennung**: Ruft alle Projekte und Geräte ab, die mit deinem Konto verknüpft sind
3. **Status-Updates**: Holt für jedes Gerät die aktuellen Statuswerte
4. **Entitäts-Updates**: Aktualisiert alle Home Assistant-Entitäten mit den neuesten Werten

Wenn ein Gerät nicht verfügbar ist (z. B. offline), werden seine Entitäten bis zum nächsten erfolgreichen Update als nicht verfügbar markiert.

## Anwendungsbeispiele

### Automation Beispiele

#### Niedriger Salz-Alarm
Benachrichtigung, wenn der Salzvorrat niedrig ist:

```yaml
automation:
  - alias: "SYR: Low Salt Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Weniger als 2 Wochen Salzvorrat
    action:
      - service: notify.mobile_app
        data:
          title: "Water Softener Alert"
          message: "Salt supply low - less than 2 weeks remaining"
```

#### Täglicher Regenerationsbericht

```yaml
automation:
  - alias: "SYR: Daily Regeneration Report"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Water Softener Daily Report"
          message: >
            Regenerations today: {{ states('sensor.syr_connect_<serial_number>_getnor') }}
            Remaining capacity: {{ states('sensor.syr_connect_<serial_number>_getres') }}L
            Salt supply: {{ states('sensor.syr_connect_<serial_number>_getss1') }} weeks
```

#### Alarm-Benachrichtigung

```yaml
automation:
  - alias: "SYR: Alarm Notification"
    trigger:
      - platform: template
        value_template: "{{ states('sensor.syr_connect_<serial_number>_getalm') != 'no_alarm' }}"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Water Softener Alarm"
          message: "Check your SYR device - alarm detected! Current alarm: {{ states('sensor.syr_connect_<serial_number>_getalm') }}"
          data:
            priority: high
```

#### Überwachung des Wasserflusses

```yaml
automation:
  - alias: "SYR: High Flow Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 20  # Durchflussrate über 20 L/min
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "High Water Flow Detected"
          message: "Unusual water flow - check for leaks!"
```

#### Geplante Regenerations-Überschreibung

```yaml
automation:
  - alias: "SYR: Weekend Regeneration"
    trigger:
      - platform: time
        at: "03:00:00"
    condition:
      - condition: time
        weekday:
          - sat
          - sun
    action:
      - service: button.press
        target:
          entity_id: button.syr_connect_<serial_number>_setsir
```

**Hinweis**: Ersetze `<serial_number>` durch die Seriennummer deines Geräts in allen Beispielen.

## Konfigurationsoptionen

### Scan-Intervall
Standardmäßig werden Daten alle 60 Sekunden aktualisiert. Du kannst dies in den Integrations-Optionen anpassen:

1. Gehe zu Einstellungen > Geräte & Dienste
2. Finde die SYR Connect Integration
3. Klicke auf „Konfigurieren"
4. Passe das Scan-Intervall (in Sekunden) an

## Deinstallation

So entfernst du die Integration aus Home Assistant:

1. Gehe zu Einstellungen > Geräte & Dienste
2. Finde die SYR Connect Integration
3. Klicke auf das Drei-Punkte-Menü (⋮)
4. Wähle „Löschen“
5. Bestätige die Löschung

Alle zugehörigen Geräte und Entitäten werden automatisch entfernt.

## Fehlerbehebung

### Diagnosedaten herunterladen

Wenn Probleme auftreten, kannst du Diagnosedaten herunterladen:

1. Gehe zu Einstellungen > Geräte & Dienste
2. Finde die SYR Connect Integration
3. Klicke auf das Gerät
4. Klicke auf das Drei-Punkte-Menü (⋮)
5. Wähle „Diagnosedaten herunterladen“

Die Datei enthält hilfreiche Informationen zur Fehlersuche (sensible Daten wie Passwörter werden automatisch entfernt).

### Verbindungsprobleme
- **Zugangsdaten prüfen**: Überprüfe Benutzername und Passwort für die SYR Connect App
- **App testen**: Melde dich in der SYR Connect App an, um zu prüfen, ob der Account funktioniert
- **Logs prüfen**: Gehe zu Einstellungen > System > Protokolle und suche nach Fehlern mit "syr_connect"
- **Netzwerk**: Stelle sicher, dass Home Assistant Internetzugang hat

### Authentifizierungsfehler
Wenn du "Authentication failed" siehst:
1. Überprüfe deine Zugangsdaten
2. Die Integration fordert zur erneuten Authentifizierung auf
3. Gehe zu Einstellungen > Geräte & Dienste
4. Klicke auf "Authentifizieren" bei der SYR Connect Integration
5. Gib deine Zugangsdaten erneut ein

### Keine Geräte gefunden
- **App-Einrichtung**: Stelle sicher, dass Geräte in der SYR Connect App richtig konfiguriert sind
- **Konto**: Verwende dasselbe Konto, das deine Geräte enthält
- **Gerätestatus**: Prüfe, ob Geräte in der SYR Connect App online sind
- **Logs**: Prüfe Home Assistant-Logs auf spezifische Fehlermeldungen

### Entitäten sind als nicht verfügbar markiert
- **Gerät offline**: Prüfe, ob das Gerät in der SYR Connect App online ist
- **Netzwerkprobleme**: Verifiziere die Internetverbindung
- **Cloud-Dienst**: Der SYR Connect-Cloud-Dienst könnte vorübergehend nicht verfügbar sein
- **Warte auf Update**: Entitäten werden nach dem nächsten erfolgreichen Update wieder verfügbar

### Hohe CPU-/Speicherauslastung
- **Scan-Intervall erhöhen**: Setze einen höheren Wert (z. B. 120–300 Sekunden) in den Integrations-Optionen

## Abhängigkeiten

Die Integration benötigt folgende Python-Pakete:
- `pycryptodomex==3.19.0`: Für AES-Verschlüsselung/-Entschlüsselung
- `defusedxml==0.7.1`: Für sichere XML-Verarbeitung (verhindert XXE-Angriffe)

**Hinweis**: Die Integration verwendet `defusedxml` für sichere XML-Verarbeitung und `pycryptodomex` (nicht `pycryptodome`), um Konflikte mit Home Assistants internen Kryptobibliotheken zu vermeiden.

Dieses Paket wird von Home Assistant automatisch installiert, wenn du:
1. Die Integration über die UI hinzufügst
2. Home Assistant nach der Installation neu startest

Für detaillierte Systemanforderungen siehe [REQUIREMENTS.md](REQUIREMENTS.md).

## Lizenz

MIT License - siehe LICENSE Datei

## Danksagungen

- Basierend auf dem Adapter [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) von TA2k.
- Vielen Dank an das SYR IoT-Entwicklungsteam für das Bereitstellen der Logos.