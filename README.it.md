![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)

# SYR Connect - Integrazione Home Assistant

![Syr](custom_components/syr_connect/logo.png)

Questa integrazione personalizzata consente il controllo dei dispositivi SYR Connect tramite Home Assistant.

## Installazione

### HACS (consigliato)

1. Apri HACS in Home Assistant
2. Vai su "Integrations"
3. Clicca i tre puntini in alto a destra
4. Seleziona "Custom repositories"
5. Aggiungi l'URL del repository
6. Seleziona la categoria "Integration"
7. Clicca "Add"
8. Cerca "SYR Connect" e installalo
9. Riavvia Home Assistant

### Installazione manuale

1. Copia la cartella `syr_connect` nella cartella `custom_components`
2. Riavvia Home Assistant

## Configurazione

1. Vai su Impostazioni > Dispositivi e servizi
2. Clicca su "+ Aggiungi integrazione"
3. Cerca "SYR Connect"
4. Inserisci le credenziali dell'app SYR Connect:
   - Nome utente
   - Password

## Funzionalità

L'integrazione crea automaticamente entità per tutti i dispositivi SYR Connect associati al tuo account.

### Dispositivi supportati

Funziona con gli addolcitori SYR visibili nel portale SYR Connect.

Testati e segnalati funzionanti:
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

Non testati, ma dovrebbero funzionare:
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect / SLIM
- SYR LEX Plus 10 IP (quando collegato tramite SYR Connect)
- SYR LEX 1500 Connect Einzel
- SYR LEX 1500 Connect Doppel
- SYR LEX 1500 Connect Pendel
- SYR LEX 1500 Connect Dreifach
- SYR IT 3000 Pendelanlage
- Altri modelli SYR con funzionalità Connect o gateway retrofit

**Nota**: Se il dispositivo è visibile nel tuo account SYR Connect, l'integrazione lo rileverà automaticamente. Per dispositivi non testati, condividere i dati diagnostici aiuta a espandere il supporto.

### Funzionalità fornite

#### Sensori
- Monitoraggio durezza acqua ingresso/uscita
- Capacità residua
- Capacità totale
- Unità di durezza
- Stato rigenerazione (attiva/inattiva)
- Numero di rigenerazioni
- Intervallo e orario di rigenerazione
- Gestione sale (volume, scorta)
- Monitoraggio pressione e flusso
- Stato operativo e allarmi

#### Sensori binari
- Rigenerazione attiva
- Stato operativo
- Allarmi

#### Pulsanti (Azioni)
- Rigenerare ora (`setSIR`)
- Rigenerazione multipla (`setSMR`)
- Resettare dispositivo (`setRST`)

### Limitazioni note

- Dipendenza dal cloud: richiede connessione Internet e servizio SYR Connect
- Intervallo minimo raccomandato: 60 secondi
- Principalmente in sola lettura: solo le azioni di rigenerazione sono disponibili
- Un solo account SYR Connect per istanza Home Assistant
- Nessuna API locale: comunicazione tramite cloud

## Aggiornamento dati

L'integrazione interroga l'API SYR Connect a intervalli regolari (default 60s):

1. Login
2. Scoperta dispositivi
3. Aggiornamento stati
4. Aggiornamento entità in Home Assistant

Se un dispositivo è offline, le entità saranno `unavailable` fino al prossimo update riuscito.

## Esempi d'uso
- Automazioni: avviso sale basso, report giornaliero rigenerazioni, notifica allarmi, monitoraggio flusso, rigenerazione pianificata (vedi README originale per esempi)

## Opzioni di configurazione

L'intervallo di scan può essere modificato nelle opzioni dell'integrazione (default 60s).

## Rimozione

1. Impostazioni > Dispositivi e servizi
2. Seleziona SYR Connect
3. Menu (⋮) > Elimina

## Risoluzione problemi

- È possibile scaricare dati diagnostici (i dati sensibili vengono mascherati)
- Errori di connessione/autenticazione: verifica credenziali, testa l'app, controlla i log

## Dipendenze

- `pycryptodomex==3.19.0`

## Licenza

Licenza MIT - vedi file LICENSE

## Ringraziamenti

- Basato sull'adapter [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) di TA2k.
- Grazie al team SYR IoT per i loghi.
