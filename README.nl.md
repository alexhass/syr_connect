<!-- markdownlint-disable-next-line MD041 -->
<img src="custom_components/syr_connect/brand/logo.png" alt="Syr" width="200">

# SYR Connect - Home Assistant-integratie

[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![syr_connect installs](https://img.shields.io/badge/dynamic/json?logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.syr_connect.total)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)
[![Quality scale: Platinum](https://img.shields.io/badge/Quality%20scale-Platinum%20%F0%9F%8F%86-b5d2e0?style=flat)](https://github.com/alexhass/syr_connect/blob/main/quality_scale.yaml)

<!-- ha-marketplace:exclude-start -->

[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

<!-- ha-marketplace:exclude-end -->

Met deze aangepaste integratie worden SYR Connect-apparaten via Home Assistant bediend. De integratie kan ook worden gebruikt met identieke apparaten van andere merken. Gemengde installaties van verschillende merken worden eveneens ondersteund.

| Merk | Link |
| ------ | ------ |
| comfort by sanibel | <https://comfort-by-sanibel.de/> |
| CONEL | <https://www.conel.de/> |
| DITECH | <https://www.ditech-haustechnik.de/> |
| Hansgrohe Pontos | <https://www.hansgrohe.de/> |
| mein concept | <https://www.mein-concept.de/> |
| mein Optima | <https://www.mein-optima.de/> |
| POLYGONVATRO | <https://www.polygongroup.com/de-DE/> |
| Reliance Valves | <https://www.rwc.com/brands/reliance-valves> |
| SYR | <https://www.syr.de/> |
| SYR Oceanic | <https://www.debestewaterbehandeling.be/> |
| TAKE | <https://take-bad.de/> |

## Schermafbeeldingen

Voorbeelden van apparaatinterfaces:

![Schermafbeelding LEXplus10S](docs/assets/screenshots/en/lexplus10s.png)

![Schermafbeelding Safe-T+](docs/assets/screenshots/en/safetplus.png)

<!-- ha-marketplace:exclude-start -->

## Installatie

[![De Home Assistant-instantie openen en een repository in de Marketplace openen.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=alexhass&repository=syr_connect&category=integration)

### Marketplace (aanbevolen)

1. Ga naar Instellingen > Marketplace.
2. Zoek naar "SYR Connect".
3. Klik op "Installeren".
4. Start Home Assistant opnieuw op.

### Handmatige installatie

1. Kopieer de map `syr_connect` naar de map `custom_components`.
2. Start Home Assistant opnieuw op.

<!-- ha-marketplace:exclude-end -->

## Configuratie

[![De Home Assistant-instantie openen en een nieuwe integratie instellen.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)

De integratie ondersteunt twee configuratiemodi:

### Instellen met de cloud-API (alle apparaten)

1. Ga naar Instellingen > Apparaten & diensten.
2. Klik op "+ Integratie toevoegen".
3. Zoek naar "SYR Connect".
4. Selecteer "Cloud".
5. Voer de inloggegevens van de mobiele app in:
   - **Service**: De app waarin de apparaten zijn ingesteld
   - **Gebruikersnaam**: Gebruikersnaam van het account in deze app
   - **Wachtwoord**: Wachtwoord van het account in deze app

### Instellen met de lokale API (alleen nieuwere apparaten)

Voor nieuwere apparaten met een lokale JSON-API, bijvoorbeeld de NeoSoft- en Trio-apparaten, SafeTech Lock, TRIO Lock, AC 3200 en RSA Connect en hun identieke apparaten van andere merken. De modelkeuze bij het instellen toont alle ondersteunde modellen:

1. Ga naar Instellingen > Apparaten & diensten.
2. Klik op "+ Integratie toevoegen".
3. Zoek naar "SYR Connect".
4. Selecteer "Lokaal".
5. Voer de apparaatgegevens in:
   - **Apparaatmodel**: Model van het apparaat (bijv. NeoSoft 2500 Connect)
   - **Hostnaam of IP-adres**: IP-adres of hostnaam van het apparaat (bijv. `192.168.178.199`)

**Opmerking**: Het IP-adres van het apparaat staat in de lijst met DHCP-clients van de router of in het displaymenu van het apparaat.

**Belangrijk**: Voor een stabiele werking moet het apparaat een **statisch IP-adres** of een **gereserveerde DHCP-lease** (DHCP-reservering) hebben. Als het IP-adres van het apparaat verandert, verliest de integratie de verbinding. Het nieuwe adres wordt ingevoerd met "Opnieuw configureren" in het menu met de drie puntjes (⋮) van de vermelding. De vermelding blijft via het serienummer aan haar apparaat gekoppeld: een ander apparaat op het nieuwe adres wordt geweigerd en moet als nieuwe vermelding worden toegevoegd. Als alternatief kan een hostnaam worden gebruikt als het netwerk lokale DNS-resolutie ondersteunt.

## Functies

De integratie maakt automatisch entiteiten aan voor alle SYR Connect-apparaten van het account.

### Ondersteunde apparaten

Deze integratie werkt met waterontharders en lekdetectieapparaten van SYR en met andere apparaten die in de SYR Connect-cloud verschijnen (via de betreffende mobiele app).

Getest en als werkend gemeld:

- CONEL CLEAR PRO FILL
- CONEL CLEAR PRO Floor Sensor
- CONEL CLEAR PRO LEAKAGE PROTECTION
- CONEL CLEAR PRO SOFT
- concept SafeFloor Floor Sensor
- DITECH Wireless Floor Sensor
- Optima T2 Floor Sensor
- POLYGONVATRO Wireless Floor Sensor
- Sanibel Leak Protection Module A25
- Sanibel Softwater UNO A25
- Sanibel Wireless Floor Sensor A25
- SYR All-in-One+
- SYR LEX 1500 Connect Single (LEX10/LEX20/LEX30/LEX40/LEX60/LEX80/LEX100)
- SYR LEX Plus 10 Connect
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect
- SYR NeoSoft 2500 Connect
- SYR SafeFloor Connect
- SYR Safe-T+ Connect
- SYR SafeTech Connect
- SYR SafeTech plus Connect
- SYR SafeTech V3 Connect
- SYR SafeTech V4 Connect
- SYR TRIO DFR/LS Connect 2425
- SYR TRIO Lock Connect
- SYR Oceanic i-LEX / Limex iQ Single (L10/L12/L15/L20/L25/L30/L40/L50/L60/L70/L80/L90/L100)

Andere apparaten zijn ook interessant, maar moeten mogelijk nog worden geïntegreerd of in elk geval worden getest (graag melden):

- CONEL CLEAR PRO MULTICONTROL-KIT
- CONEL CLEAR PRO SOFT TWIN
- concept 200 Dual Water Softener
- concept 200 Replacement Filter
- concept 300 Automatic Backwash RSA
- concept 300 Trio Filter with Leak Protection
- concept Dual Water Softener
- concept Single Water Softener
- DITECH Automatic Backwash HWS/RF
- DITECH Backwash Filter Protect
- DITECH Connection Module Plus
- DITECH Dual Water Softener
- DITECH Hygiene Flush Box
- DITECH Single Water Softener
- Hansgrohe PontosBase
- Optima Dual Water Softener
- Optima Single Water Softener
- Optima T Replacement Filter
- Optima T2 Dual Water Softener
- POLYGONVATRO SafeTech Connect (verkocht bij de opstalverzekering van AXA als "Wasserwächter")
- RWC MultiSafe Floor Leak Sensor
- RWC MultiSafe Leak Detector Control Valve
- Sanibel Automatic Backwash System RSA A25
- Sanibel Softwater DUO A25
- SYR AC 3200 Connect
- SYR AC All-in-One 3228 Connect
- SYR CONTROLICmini
- SYR HVA
- SYR HygBox Connect
- SYR Hygiene Module (koud / warm / koud en warm)
- SYR Inliner-HWA 3300
- SYR IT 3000 Pendulum system
- SYR LEX 1500 Connect Alternating
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Triple
- SYR NeoDos Connect
- SYR NeoSoft 5000 Connect
- SYR NeoSoft Lock Connect I / II
- SYR RSA Connect
- SYR Safe-T Communication Module
- SYR Safe-T Hygiene Module
- SYR Safe-T Master / Slave
- SYR SafeTech Lock Connect
- SYR Trio LS Connect
- TAKE Dual Water Softener
- TAKE Single Water Softener

**Opmerking**: Als een apparaat zichtbaar is in het SYR Connect-account, vindt de integratie het en maakt ze de entiteiten automatisch aan. Voor een "niet-getest apparaat" helpt het delen van de diagnostische gegevens om onbekende waarden te vinden en te controleren of alles werkt zoals bedoeld. Zo kan ook de lijst met geteste apparaten worden uitgebreid.

### Niet-ondersteunde apparaten

- SYR Oceanic Limex SMART COMPACT/MINI/MAXI-apparaten. Deze apparaten gebruiken een ander cloudportaal (`i-lexconnect.com`) in plaats van de SYR Connect-clouddienst. Het zijn Husty SaoCal-apparaten onder een andere merknaam.
- Husty SaoCal-apparaten. Zie [husty_integration_home_assistant](https://github.com/trafopowielacz/husty_integration_home_assistant).

### Ondersteunde functionaliteit

#### Sensoren

De integratie biedt een uitgebreide bewaking van de apparaten:

#### Waterkwaliteit en capaciteit

- Bewaking van de ruw- en zachtwaterhardheid
- Geleidbaarheid van het water (µS/cm)
- Waterhardheidsbereik (zacht, gemiddeld, hard), geschat op basis van de geleidbaarheid (SafeTech-familie)
- Geleidbaarheidsfactor
- Watertemperatuur (°C)
- Bijhouden van de resterende onthardingscapaciteit
- Harscapaciteit per tank (tot 3 tanks, %)
- Bewaking van het totale volume
- Weergave van de waterhardheidseenheid

#### Regeneratie-informatie

- Regeneratiestatus en indicator van de actieve tank (tot 3 tanks)
- Regeneratiemodus (Standaard / ECO / Power / Automatisch)
- Aantal uitgevoerde regeneraties
- Tijdstip van de laatste regeneratie
- Instellingen van het regeneratie-interval
- Regeneratieschema
- Cyclustellers en tijden

#### Zoutbeheer

- Zouthoeveelheid in de containers (1–3)
- Zoutvoorraad (resterende weken)
- Reservecapaciteit van de hars per fles

#### Systeembewaking

- Bewaking van de waterdruk
- Doorstroming (actueel en momentaan)
- Doorstromingsteller (totaal verbruik)
- Batterij- en netspanning
- Status van alarmen, meldingen en waarschuwingen (huidige code en de laatste 8 vermeldingen in de geschiedenis)

#### Lekbescherming (LEXplus10SL / Trio DFR/LS)

- Volume- en duurlimieten van de lekbescherming (aanwezig- en afwezigprofiel)
- Index van het actieve lekbeschermingsprofiel
- Lekbeschermingsprofielen 1–8 (volumelimiet, maximale duur, doorstromingsdrempel, waarschuwings- en zoemervlaggen)
- Timer voor tijdelijke uitschakeling
- Lekwaarschuwingsdrempel (%)

#### Microlektest (Trio DFR/LS, SafeTech, SafeTech+, TRIO Lock, SafeTech Lock)

- Interval en status van de microlektest
- Testduur en aantal gebeurtenissen

#### Zelflerende fase (Trio DFR/LS, SafeTech+, TRIO Lock, SafeTech Lock)

- Resterende en verstreken zelfleertijd
- Doorstroming en opgebouwd volume tijdens het zelfleren
- Instellingen van het zelfleren: marge voor volume en tijd, marge voor doorstroming, minimale doorstroming

#### Vloersensor (SafeFloor)

- Huidige luchtvochtigheid en temperatuur
- Batterijniveau (%)
- Alarmstatus

#### Filter en terugspoeling

- Filtertype (SafeTech, SafeTech Lock, TRIO Lock, AC All-in-One 3228 Connect)
- IJzergehalte (LEX-familie)
- Tellers van automatische en handmatige terugspoelingen (automatische terugspoeling RSA)

#### Onderhoud

- Volgende geplande onderhoudsdata (halfjaarlijks en jaarlijks)
- Verwacht dagelijks waterverbruik

#### Apparaatinformatie

- Serienummer
- Firmwareversie en model
- Apparaattype en fabrikant
- Netwerkinformatie (IP, MAC, gateway)
- Status van de Wi-Fi-verbinding en signaalsterkte
- Tijdzone (UTC-verschil)

#### Binaire sensoren

- **Zoemer bij alarm**: Geeft aan of de zoemer bij een alarm klinkt.
- **Lekbescherming**: Geeft aan of de lekbescherming actief of uitgeschakeld is.
- **Kleptest**: Geeft aan of er een kleptest loopt.
- **Firmwarecontrole**: Geeft aan of er nieuwe firmware beschikbaar is (gecontroleerd bij het opstarten en elke 6 uur).
- **Zomertijd**: Geeft aan of het apparaat automatisch overschakelt naar zomertijd.
- **Temperatuursensor**, **Druksensor**, **Geleidbaarheidssensor**: Geven aan of de meetsensor actief of uitgeschakeld is.
- **Vloersensorbewaking**: Geeft aan of de bewaking van de vloersensoren is ingeschakeld.

#### Knoppen (acties)

- **Nu regenereren**: Een onmiddellijke regeneratie starten. Dit wordt geweigerd zolang er een regeneratie loopt.
- **Alarm resetten**: Actieve alarmmeldingen wissen.
- **Melding resetten**: Meldingen wissen.
- **Waarschuwing resetten**: Waarschuwingen wissen.
- **Microlektest starten**: De microlektest starten. De klep blijft ongeveer 4 minuten gesloten, en water tappen tijdens de test leidt tot een negatief resultaat (alleen lokale API).
- **Handmatige spoeling (koud water)**, **Handmatige spoeling (warm water)**: Een handmatige spoeling van de waterleiding starten (hygiënemodule).

#### Schakelaars

- **Zoemer bij alarm**: De zoemer bij een alarm in- of uitschakelen.
- **Profielwissel op het apparaat toestaan**: Het wisselen van het lekbeschermingsprofiel met de knop op het apparaat toestaan of blokkeren.
- **Vulmodus**: Het automatisch vullen in- of uitschakelen (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect en zijn identieke apparaten van andere merken, All-in-One+).
- **Eerste vulling**: De eerste vulling starten of stoppen (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect en zijn identieke apparaten van andere merken, All-in-One+).
- **Handmatig vullen**: Het handmatig vullen starten of stoppen (All-in-One+).
- **Automatische terugspoeling**: De automatische terugspoeling in- of uitschakelen (automatische terugspoeling RSA).
- **Terugspoelherinnering**: De herinnering aan de terugspoeling in- of uitschakelen (automatische terugspoeling RSA).
- **Stagnatiespoeling**, **Temperatuurspoeling**, **Periodieke spoeling**: De drie spoelfuncties in- of uitschakelen (HygBox).

#### Keuzelijsten (configuratie)

- **Regeneratietijd**: De dagelijkse regeneratietijd instellen (intervallen van 15 minuten).
- **Actief lekbeschermingsprofiel**: Het actieve lekbeschermingsprofiel selecteren (bij apparaten met meerdere profielen).
- **Zouthoeveelheid in container 1–3**: De zouthoeveelheid per container instellen (afhankelijk van het model, tot 3 containers).
- **Regeneratie-interval**: Instellen hoe vaak de regeneratie plaatsvindt (afhankelijk van het model: tot 3, 4 of 99 dagen).
- **Displayoriëntatie**: De oriëntatie van het display instellen (0 / 90 / 180 / 270 graden, bij apparaten met display).
- **Apparaattaal**: De taal van het display van het apparaat instellen: Duits, Engels, Spaans, Italiaans of Pools (SafeTech).
- **Regeneratiemodus**: Standaard / ECO / Power / Automatisch selecteren (bij apparaten die dit ondersteunen).
- **Ruwwaterhardheid**, **Zachtwaterhardheid**: De hardheid van het ruwe en het onthard water instellen (LEX-familie, CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect en zijn identieke apparaten van andere merken, All-in-One+). De eenheid volgt de op het apparaat ingestelde hardheidseenheid (°dH, °fH, °e, mg/l CaCO₃, ppm, mmol/l of mval/l).
- **Waterbehandeling en vullen** (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect en zijn identieke apparaten van andere merken, All-in-One+): Grootte en type van de patroon, zachtwaterhardheid of maximale uitgangsgeleidbaarheid (afhankelijk van de patroon), vulperiode, aantal vulcycli, maximale vulduur en -hoeveelheid, doeldruk, waarschuwingsdrempel resterende capaciteit, maximaal vulvolume en maximale vulduur van de eerste vulling.
- **Vloersensor** (SafeFloor): Alarmduur, minimale en maximale drempels voor luchtvochtigheid en temperatuur ("Uit" schakelt een drempel uit), meetinterval en synchronisatie-interval van de instellingen.
- **Hygiënespoeling** (HygBox): Watertype, stagnatietijd en spoelvolume, start- en stoptemperatuur, maximale spoelduur en spoelingen per dag, interval en spoelvolume van de periodieke spoeling, synchronisatie-interval van de instellingen.
- **Hygiënespoeling** (hygiënemodule, Safe-T Hygiene Module): Stagnatietijd, spoelinterval, temperatuurgrens, maximale spoelduur en maximaal spoelvolume van de koud- en de warmwaterleiding.
- **Dosering** (NeoDos Connect): Grootte van de jerrycan, doseervloeistof en bedrijfsmodus.
- **Terugspoeling** (automatische terugspoeling RSA): Terugspoelinterval en terugspoelherinneringsinterval (1–365 dagen).
- **Lekbescherming** (Safe-T+): Lekbeschermingsniveau bij aanwezigheid en bij afwezigheid (een niveau bij afwezigheid schakelt naar het afwezigheidsprofiel, „Uit” terug naar het aanwezigheidsprofiel), lektijd en tijdelijk uitschakelen van de lekbescherming.

#### Klepbediening

- **Klepafsluiting**: De hoofdafsluiter van het water bedienen.
  - Klep openen en sluiten.
  - Huidige klepstand en status bewaken.
  - Integratie met lekdetectie-automatiseringen voor automatisch afsluiten.

#### Firmware-update

- **Firmware-update**: Geeft aan of er nieuwe firmware beschikbaar is en installeert deze. Het apparaat moet met internet verbonden zijn. Het apparaat meldt het nummer van de nieuwe versie niet.

### API-modi

De integratie ondersteunt twee API-modi:

#### Cloud-API (op basis van XML)

- **Ondersteund door**: Alle SYR Connect-apparaten
- **Verbinding**: Via de SYR Connect-clouddienst
- **Authenticatie**: Gebruikersnaam en wachtwoord van het SYR Connect-account
- **Voordelen**: Werkt met alle apparaatmodellen, toegang op afstand vanaf elke locatie
- **Vereisten**: Internetverbinding, SYR Connect-account

#### Lokale API (op basis van JSON)

- **Ondersteund door**: Nieuwere modellen met een ingebouwde lokale API, bijvoorbeeld NeoSoft, Trio DFR/LS, TRIO Lock, SafeTech Lock, AC 3200, RSA, Pontos Base, All-in-One+, HygBox en nieuwere SafeTech-varianten, ook van andere merken. De modelkeuze bij het instellen toont alle ondersteunde modellen.
- **Verbinding**: Rechtstreeks met het apparaat via het lokale netwerk (poort 5333).
- **Authenticatie**: Geen inloggegevens nodig.
- **Voordelen**: Geen afhankelijkheid van internet, snellere reactietijden, geen aanvraaglimieten van de cloud.
- **Vereisten**: Het apparaat moet zich in hetzelfde netwerk als Home Assistant bevinden en heeft een statisch IP-adres of een hostnaam nodig.

De API-modus wordt bij het instellen gekozen (Cloud of Lokaal).

## Hoe gegevens worden bijgewerkt

De integratie vraagt de API van het apparaat met regelmatige tussenpozen op (standaard: 60 seconden). Het bijwerkproces hangt af van de API-modus:

### Bijwerkproces met de cloud-API

1. **Inloggen**: Authenticeert zich bij de SYR Connect-cloud-API met de inloggegevens.
2. **Apparaatdetectie**: Haalt alle projecten en apparaten van het account op, bij het opstarten en daarna elke 30 minuten. Een apparaat dat uit het account is verwijderd, wordt samen met zijn entiteiten uit Home Assistant verwijderd.
3. **Statusupdates**: Haalt voor elk apparaat de huidige status op met alle sensorwaarden.
4. **Entiteitupdates**: Werkt alle Home Assistant-entiteiten bij met de nieuwste waarden.

### Bijwerkproces met de lokale API

1. **Statusupdates**: Haalt de apparaatstatus rechtstreeks op bij het lokale eindpunt.
2. **Entiteitupdates**: Werkt alle Home Assistant-entiteiten bij met de nieuwste waarden.

De lokale API is sneller en hangt niet af van de internetverbinding, waardoor ze betrouwbaarder is voor realtime bewaking en automatiseringen.

Als een update tijdelijk mislukt (bijv. time-out, onderhoud van de cloud of een onvolledig antwoord), behouden de entiteiten hun laatste waarden en wordt de fout in het logboek geschreven. Entiteiten worden alleen onbeschikbaar wanneer de cloud het apparaat als offline meldt. Ze blijven onbeschikbaar tot het apparaat weer een volledige status verstuurt.

Zolang er helemaal geen gegevens kunnen worden opgehaald, vraagt de integratie minder vaak op: het interval verdubbelt na elke mislukte update, tot 15 minuten. De eerste geslaagde update herstelt het ingestelde interval.

Als er langer dan 1 uur geen gegevens kunnen worden opgehaald, wordt de storing niet meer als tijdelijk beschouwd: de betrokken entiteiten worden onbeschikbaar en er verschijnt een melding onder **Instellingen** → **Reparaties**. Beide verdwijnen zodra er weer gegevens worden opgehaald.

### Meetgeschiedenis van de SafeFloor

Een SafeFloor meet regelmatig temperatuur en luchtvochtigheid, maar stuurt zijn metingen slechts om de paar dagen naar de cloud, zodat zijn sensoren een vlakke lijn gevolgd door een sprong tonen. De integratie haalt de afzonderlijke metingen elke 12 uur op uit de cloud en slaat ze op als statistieken met de naam van de sensoren (bijv. "Bijkeuken Temperatuur"). Om de werkelijke curve te zien, wordt een kaart aan een dashboard toegevoegd:

1. Open het dashboard en selecteer rechtsboven **Dashboard bewerken**.
2. Selecteer **Kaart toevoegen**, typ `Statistics` in **Kaarten zoeken** en kies **Statistiekgrafiek**.
3. Selecteer **Code-editor weergeven**, vervang de tekst door een van de onderstaande fragmenten en selecteer **Opslaan**.
4. Selecteer **Klaar**.

`123456789` wordt vervangen door het serienummer van de SafeFloor. Per meting is één kaart nodig.

Temperatuur:

```yaml
type: statistics-graph
title: Temperatuur
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_getcel_history
```

Luchtvochtigheid:

```yaml
type: statistics-graph
title: Luchtvochtigheid
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_gethmd_history
```

De cloud bewaart alleen de metingen van de laatste 6 dagen. Het synchronisatie-interval van de sensor moet 6 dagen of minder blijven, anders gaan metingen verloren. De statistieken worden samen met het apparaat verwijderd.

### Bekende beperkingen

- **Afhankelijkheid van de cloud**: De cloud-API vereist een actieve internetverbinding en een werkende clouddienst.
- **Update-interval**: De cloud-API staat een update-interval van ten minste 60 seconden toe, de lokale API van ten minste 10 seconden.
- **Beperkte schrijftoegang**: Configuratiewijzigingen (regeneratietijd, zouthoeveelheden, intervallen) en bedieningsacties (regeneratie, klepbediening) worden ondersteund, maar sommige geavanceerde instellingen zijn mogelijk alleen beschikbaar in de SYR Connect-app.
- **Ondersteuning van de lokale API**: Niet elk model biedt een lokale JSON-API. LEX 1500, LEXplus, i-LEX, Safe-T, SafeFloor, HVA, hygiënemodules en oudere SafeTech-varianten vereisen toegang via de cloud-API.

## Toepassingen en voorbeelden

### Voorbeelden van automatiseringen

De voorbeelden gebruiken de YAML-syntaxis van `configuration.yaml`. In alle voorbeelden wordt `<serial_number>` vervangen door het serienummer van het apparaat en `<device_name>` door de naam van het apparaat van de mobiele app in Home Assistant.

#### Waarschuwing bij weinig zout

Melding wanneer de zoutvoorraad bijna op is:

```yaml
automation:
  - alias: "SYR: Waarschuwing bij weinig zout"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Minder dan 2 weken zout over
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Waterontharder"
          message: "Zoutvoorraad laag - minder dan 2 weken over"
```

#### Dagelijks regeneratierapport

Dagelijks overzicht van de regeneraties, de resterende capaciteit en de zoutvoorraad:

```yaml
automation:
  - alias: "SYR: Dagelijks regeneratierapport"
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Dagelijks rapport van de waterontharder"
          message: >
            Regeneraties (totaal): {{ states('sensor.syr_connect_<serial_number>_getnor') }}
            Resterende capaciteit: {{ states('sensor.syr_connect_<serial_number>_getres') }} L
            Zoutvoorraad: {{ states('sensor.syr_connect_<serial_number>_getss1') }} weken
```

#### Alarmmelding

Onmiddellijke melding wanneer het apparaat een alarm meldt:

```yaml
automation:
  - alias: "SYR: Alarmmelding"
    triggers:
      - trigger: template
        value_template: >
          {{ states('sensor.syr_connect_<serial_number>_getala')
             not in ['no_alarm', 'unknown', 'unavailable'] }}
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "⚠️ SYR-alarm"
          message: "Huidig alarm: {{ states('sensor.syr_connect_<serial_number>_getala') }}"
          data:
            priority: high
```

#### Bewaking van de waterdoorstroming

Waarschuwing bij een ongewoon hoge waterdoorstroming gedurende meerdere minuten (mogelijk lek):

```yaml
automation:
  - alias: "SYR: Waarschuwing bij hoge doorstroming"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 1200  # Doorstroming boven 1200 l/h (20 l/min)
        for:
          minutes: 5
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Hoge waterdoorstroming gedetecteerd"
          message: "Ongewone waterdoorstroming - mogelijk lek"
```

#### Leksensor: waterklep sluiten

Sluit de SYR-waterafsluiter met de standaardactie `valve.close` wanneer een leksensor water detecteert. De entiteit-ID's worden vervangen door de ID's die in de installatie worden gebruikt. Deze automatisering kan een kritieke veiligheidsactie worden en moet daarom zeer zorgvuldig worden getest.

```yaml
automation:
  - alias: "SYR: Klep sluiten bij lek"
    triggers:
      - trigger: state
        entity_id: binary_sensor.house_leak_sensor
        to: "on"
    actions:
      - action: valve.close
        target:
          entity_id: valve.syr_connect_<serial_number>_getab
      - action: notify.mobile_app_<device_name>
        data:
          title: "SYR: Lek gedetecteerd - klep gesloten"
          message: "Waterlek gedetecteerd - de SYR-waterafsluiter is automatisch gesloten."
```

#### Regeneratie in het weekend

Start op zaterdag en zondag om 03:00 een regeneratie:

```yaml
automation:
  - alias: "SYR: Regeneratie in het weekend"
    triggers:
      - trigger: time
        at: "03:00:00"
    conditions:
      - condition: time
        weekday:
          - sat
          - sun
    actions:
      - action: button.press
        target:
          entity_id: button.syr_connect_<serial_number>_setsir
```

## Configuratieopties

### Update-interval

De gegevens worden standaard elke 60 seconden bijgewerkt. Het interval wordt ingesteld in de opties van de integratie: ten minste 60 seconden voor de cloud, ten minste 10 seconden voor lokale apparaten en in beide gevallen ten hoogste 600 seconden.

1. Open Instellingen > Apparaten & diensten.
2. Open de SYR Connect-integratie.
3. Selecteer "Configureren".
4. Pas het update-interval aan (in seconden).

## Verwijderen

Zo wordt de integratie uit Home Assistant verwijderd:

1. Ga naar Instellingen > Apparaten & diensten.
2. Zoek de SYR Connect-integratie.
3. Klik op het menu met de drie puntjes (⋮).
4. Selecteer "Verwijderen".
5. Bevestig het verwijderen.

Alle bijbehorende apparaten en entiteiten worden automatisch verwijderd.

## Probleemoplossing

### Diagnostische gegevens downloaden

Bij problemen helpen de diagnostische gegevens van de vermelding van de integratie. Ze bevatten de gegevens van alle apparaten van de vermelding:

1. Open Instellingen > Apparaten & diensten.
2. Open de SYR Connect-integratie.
3. Open het menu met de drie puntjes (⋮) van de vermelding (account of lokaal apparaat).
4. Selecteer "Diagnostische gegevens downloaden".

Wachtwoorden, gebruikersnamen, sessiegegevens, het codenummer van het apparaat, IP-adressen, gateways en de naam van het Wi-Fi-netwerk worden uit het bestand verwijderd, en het serienummer wordt gemaskeerd.

### Debuglogboeken

Het in- en uitschakelen van debuglogboeken wordt beschreven in [docs/howto-debugging.md](docs/howto-debugging.md) (in het Engels).

### Verbinding mislukt

- **Inloggegevens controleren**: De gebruikersnaam en het wachtwoord van de SYR Connect-app controleren.
- **App testen**: Het inloggen in de mobiele SYR Connect-app moet met hetzelfde account werken.
- **Logboeken controleren**: Ga naar Instellingen > Systeem > Logboeken en zoek naar fouten van "syr_connect".
- **Netwerkproblemen**: Home Assistant moet toegang tot internet hebben.

### Authenticatiefouten

Bij fouten "Authentication failed":

1. De inloggegevens controleren.
2. De integratie vraagt om een nieuwe authenticatie.
3. Ga naar Instellingen > Apparaten & diensten.
4. Klik op "Authenticeren" bij de SYR Connect-integratie.
5. Voer de inloggegevens opnieuw in.

De nieuwe authenticatie en "Opnieuw configureren" wijzigen alleen het wachtwoord van het account. Een andere gebruikersnaam is een ander account: die wordt daar geweigerd en moet als nieuwe vermelding worden toegevoegd.

### Geen apparaten gevonden

- **App-instellingen**: De apparaten moeten correct zijn ingesteld in de SYR Connect-app.
- **Toegang tot het account**: Het account moet het account zijn waarin de apparaten zijn ingesteld.
- **Apparaatstatus**: Controleren of de apparaten online zijn in de SYR Connect-app.
- **Logboeken**: De logboeken van Home Assistant controleren op specifieke foutmeldingen.

### Entiteiten worden als onbeschikbaar weergegeven

- **Apparaat offline**: De cloud meldt het apparaat als offline. De stroomvoorziening en de netwerkverbinding van het apparaat moeten worden gecontroleerd.
- **SYR Connect-app**: Het apparaat moet in de SYR Connect-app als online worden weergegeven.
- **Weer online**: De entiteiten worden weer beschikbaar zodra het apparaat een volledige status verstuurt.

- **Langer dan 1 uur geen verbinding**: Er konden langer dan 1 uur geen gegevens van de cloud of het apparaat worden opgehaald. Er verschijnt een melding onder **Instellingen** → **Reparaties**. De internetverbinding en de status van de SYR Connect-cloud moeten worden gecontroleerd.
- **Netwerkprobleem**: Als de hostnaam niet kon worden omgezet of er geen verbinding kon worden geopend, noemt de melding het netwerk als oorzaak. De netwerkverbinding en de DNS-instellingen van Home Assistant moeten worden gecontroleerd, bij een lokaal apparaat ook het IP-adres ervan.

Tijdelijke problemen met de verbinding of de clouddienst maken entiteiten niet onbeschikbaar. De entiteiten behouden hun laatste waarden en de fout wordt in het logboek geschreven.

### Hoog CPU- of geheugengebruik

- **Update-interval verhogen**: Een hogere waarde (bijv. 120–300 seconden) instellen in de opties van de integratie.
- Dit vermindert de API-aanroepen en de systeembelasting.

<!-- ha-marketplace:exclude-start -->

## Afhankelijkheden

De integratie heeft de volgende Python-pakketten nodig:

- `pycryptodomex>=3.19.0,<4.0`: Voor AES-versleuteling en -ontsleuteling
- `defusedxml>=0.7.1,<1.0`: Voor het veilig verwerken van XML (voorkomt XXE-aanvallen)

**Opmerking**: De integratie gebruikt `defusedxml` voor het veilig verwerken van XML en `pycryptodomex` (niet `pycryptodome`) om conflicten met de ingebouwde cryptografische bibliotheken van Home Assistant te voorkomen.

Home Assistant installeert de pakketten **automatisch** wanneer:

1. De integratie via de gebruikersinterface wordt toegevoegd.
2. Home Assistant na de installatie opnieuw wordt opgestart.

Gedetailleerde systeemvereisten en probleemoplossing staan in [REQUIREMENTS.md](REQUIREMENTS.md) (in het Engels).

<!-- ha-marketplace:exclude-end -->

## Disclaimer

### BELANGRIJK: Lees dit voordat de integratie wordt gebruikt

Deze integratie bedient systemen voor waterbehandeling en waterafsluiting. Een onjuiste configuratie of slecht werkende automatiseringen kunnen leiden tot waterschade, systeemstoringen of materiële schade.

- **Gebruik op eigen risico**: Deze software wordt geleverd "zoals hij is", zonder enige vorm van garantie.
- **Grondig testen**: Automatiseringen moeten altijd onder veilige omstandigheden worden getest voordat ze in gebruik worden genomen.
- **Kritieke systemen**: Automatiseringen voor de klepbediening kunnen de volledige watertoevoer afsluiten en moeten zorgvuldig worden getest.
- **Geen aansprakelijkheid**: De auteurs en bijdragers zijn niet verantwoordelijk voor schade, waterschade, materiële schade of andere problemen die voortvloeien uit het gebruik van deze integratie.
- **Afhankelijkheid van de cloud**: Deze integratie is afhankelijk van de SYR Connect-clouddienst, waarvan de beschikbaarheid niet gegarandeerd is.
- **Noodplan**: Er moet een alternatieve toegang tot de waterafsluiter bestaan voor het geval het systeem uitvalt.

Wie deze integratie installeert en gebruikt, erkent deze risico's en gaat ermee akkoord haar verantwoord te gebruiken.

## Licentie

Apache License 2.0, zie [LICENSE](LICENSE)

## Dankwoord

- Geïnspireerd door de [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp)-adapter van TA2k.
- Hartelijk dank aan het SYR IoT-Development-Team voor het delen van de logo's.
