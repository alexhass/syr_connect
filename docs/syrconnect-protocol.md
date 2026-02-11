# SYR Connect Protocol

The SYR water softening units of the LEX Plus series, e.g. LEX Plus 10 Connect or LEX Plus 10 S Connect, are sharing their status with the SYR Connect cloud and receiving commands and settings changes from it. The SYR Connect cloud can be either accessed through the [SYR Connect web interface](https://syrconnect.de/) or the [SYR App](https://www.syr.de/de/SYR_App).

The protocol between SYR water softening unit and SYR Connect cloud is partially reverse engineered through analyzing the exchanged messages. A LEX Plus 10 S Connect with firmware SLPS 1.7 was used for this analysis; later SLSP 1.9 was analysed. Additionally, a LEX Plus 10 SL Connect was analyzed that contains an integrated leakage detection device, called Safeconnect.  

## Communication

The communication happens for firmware version 1.7 via http to syrconnect.consoft.de and connect.saocal.pl. Both domains seem to use the same protocol, but only the former seems to be used for the SYR Connect cloud. Both domains are resolved via DNS, which means the communication can easily be redirected by using a DNS server (either via DHCP or via static configuration) that resolves these domains to the desired server IP. With firmware version 1.9 https is used instead of http, but no certificate checking seems to happen. The
used domains changed to syrconnect.de and maintenance.syrconnect.de but the communication protocol is still the same.

The water softening unit is querying two webservices via the request method 'POST' and parameter 'xml':

- GetBasicCommands:  
  Full address (SLSP 1.7): syrconnect.consoft.de/WebServices/SyrConnectLimexWebService.asmx/GetBasicCommands  
  Full address (SLSP 1.9): syrconnect.de/WebServices/SyrConnectLimexWebService.asmx/GetBasicCommands  
  Alternative (SLSP 1.7): connect.saocal.pl/GetBasicCommands  
  Alternative (SLSP 1.9): maintenance.syrconnect.de/GetBasicCommands
- GetAllCommands:  
  Full address (SLSP 1.7): syrconnect.consoft.de/WebServices/SyrConnectLimexWebService.asmx/GetAllCommands  
  Full address (SLSP 1.9): syrconnect.de/WebServices/SyrConnectLimexWebService.asmx/GetAllCommands  
  Alternative (SLSP 1.7): connect.saocal.pl/GetAllCommands  
  Alternative (SLSP 1.9): maintenance.syrconnect.de/GetAllCommands

The water softening unit is asking the server in an interval of ~10s for new commands which are actually remote procedure calls from the server to the unit. The response to these commands is then sent from the unit to the server in the next request. The commands are either getter or setters for certain properties of the water softening unit.

The following shows a sample conversation between unit and server (confidential values like SRN and MAC have been replaced by dummy values):

#### First request

The first request is to the web service GetBasicCommands which basically requests the unit to identify:

- Queried URL: <http://syrconnect.consoft.de/WebServices/SyrConnectLimexWebService.asmx/GetBasicCommands>
- POST-Parameters: *nothing*
- Server response:  

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc version="1.0">
    <d>
      <c n="getSRN" v="" />
      <c n="getVER" v="" />
      <c n="getFIR" v="" />
      <c n="getTYP" v="" />
      <c n="getCNA" v="" />
    </d>
  </sc>
  ```

#### Second Request

The second request is to the web service GetAllCommands and answers the previous request:

- Queried URL: <http://syrconnect.consoft.de/WebServices/SyrConnectLimexWebService.asmx/GetAllCommands>
- POST-Parameters 'xml' (url-encoded):

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc version="1.0">
    <d>
      <c n="getSRN" v="123456789" />
      <c n="getVER" v="1.7" />
      <c n="getTYP" v="80" />
      <c n="getCNA" v="LEXplus10S" />
    </d>
  </sc>
  ```

- Server response:  

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc version="1.0">
    <d>
      <c n="getSRN" v="" />
      <c n="getVER" v="" />
      <c n="getFIR" v="" />
      <c n="getTYP" v="" />
      <c n="getCNA" v="" />
      <c n="getALM" v="" />
      <c n="getCDE" v="" />
      <c n="getCS1" v="" />
      <c n="getCS2" v="" />
      <c n="getCS3" v="" />
      <c n="getCYN" v="" />
      <c n="getCYT" v="" />
      <c n="getDEN" v="" />
      <c n="getDGW" v="" />
      <c n="getDWF" v="" />
      <c n="getFCO" v="" />
      <c n="getFLO" v="" />
      <c n="getINR" v="" />
      <c n="getIPA" v="" />
      <c n="getIWH" v="" />
      <c n="getLAR" v="" />
      <c n="getMAC" v="" />
      <c n="getMAN" v="" />
      <c n="getNOR" v="" />
      <c n="getNOT" v="" />
      <c n="getOWH" v="" />
      <c n="getPRS" v="" />
      <c n="getPST" v="" />
      <c n="getRDO" v="" />
      <c n="getRES" v="" />
      <c n="getRG1" v="" />
      <c n="getRG2" v="" />
      <c n="getRG3" v="" />
      <c n="getRPD" v="" />
      <c n="getRPW" v="" />
      <c n="getRTH" v="" />
      <c n="getRTI" v="" />
      <c n="getRTM" v="" />
      <c n="getSCR" v="" />
      <c n="getSIR" v="" />
      <c n="getSRE" v="" />
      <c n="getSS1" v="" />
      <c n="getSS2" v="" />
      <c n="getSS3" v="" />
      <c n="getSTA" v="" />
      <c n="getSV1" v="" />
      <c n="getSV2" v="" />
      <c n="getSV3" v="" />
      <c n="getTOR" v="" />
      <c n="getVS1" v="" />
      <c n="getVS2" v="" />
      <c n="getVS3" v="" />
      <c n="getWHU" v="" />
    </d>
  </sc>
  ```

#### Third and following requests

The third request and all following requests are also to GetAllCommands answering the previous requests:

- Queried URL: <http://syrconnect.consoft.de/WebServices/SyrConnectLimexWebService.asmx/GetAllCommands>
- POST-Parameters 'xml' (url-encoded):

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc version="1.0">
    <d>
      <c n="getSRN" v="123456789" />
      <c n="getVER" v="1.7" />
      <c n="getTYP" v="80" />
      <c n="getCNA" v="LEXplus10S" />
      <c n="getALM" v="" />
      <c n="getCDE" v="010SCA19DF0917.01.024.1.1.0010" />
      <c n="getCS1" v="44" />
      <c n="getCS2" v="0" />
      <c n="getCS3" v="0" />
      <c n="getCYN" v="0" />
      <c n="getCYT" v="00:00" />
      <c n="getDEN" v="1" />
      <c n="getDGW" v="123.123.123.1" />
      <c n="getDWF" v="200" />
      <c n="getFCO" v="0" />
      <c n="getFIR" v="SLPS" />
      <c n="getFLO" v="0" />
      <c n="getHED" v="2" />
      <c n="getHEM" v="9" />
      <c n="getHEY" v="2023" />
      <c n="getHSD" v="2" />
      <c n="getHSM" v="9" />
      <c n="getHSY" v="0" />
      <c n="getIPH" v="" />
      <c n="getIWH" v="14" />
      <c n="getMAC" v="01:23:45:67:89:AB" />
      <c n="getMAN" v="Syr" />
      <c n="getNOT" v="" />
      <c n="getOWH" v="7" />
      <c n="getPA1" v="0" />
      <c n="getPA2" v="0" />
      <c n="getPA3" v="0" />
      <c n="getPRS" v="40" />
      <c n="getPST" v="1" />
      <c n="getRDO" v="90" />
      <c n="getRES" v="1392" />
      <c n="getRG1" v="0" />
      <c n="getRG2" v="0" />
      <c n="getRG3" v="0" />
      <c n="getRPD" v="4" />
      <c n="getRPW" v="0" />
      <c n="getRTH" v="16" />
      <c n="getRTI" v="00:00" />
      <c n="getRTM" v="0" />
      <c n="getSCR" v="0" />
      <c n="getSRE" v="0" />
      <c n="getSS1" v="3" />
      <c n="getSS2" v="0" />
      <c n="getSS3" v="0" />
      <c n="getSTA" v="" />
      <c n="getSV1" v="12" />
      <c n="getSV2" v="0" />
      <c n="getSV3" v="0" />
      <c n="getTOR" v="423" />
      <c n="getVAC" v="0" />
      <c n="getVS1" v="0" />
      <c n="getVS2" v="0" />
      <c n="getVS3" v="0" />
      <c n="getWHU" v="0" />
    </d>
  </sc>
  ```

- Server response:  

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc version="1.0">
    <d>
      <c n="getSRN" v="" />
      <c n="getVER" v="" />
      <c n="getFIR" v="" />
      <c n="getTYP" v="" />
      <c n="getCNA" v="" />
      <c n="getALM" v="" />
      <c n="getCDE" v="" />
      <c n="getCS1" v="" />
      <c n="getCS2" v="" />
      <c n="getCS3" v="" />
      <c n="getCYN" v="" />
      <c n="getCYT" v="" />
      <c n="getDEN" v="" />
      <c n="getDGW" v="" />
      <c n="getDWF" v="" />
      <c n="getFCO" v="" />
      <c n="getFLO" v="" />
      <c n="getINR" v="" />
      <c n="getIPA" v="" />
      <c n="getIWH" v="" />
      <c n="getLAR" v="" />
      <c n="getMAC" v="" />
      <c n="getMAN" v="" />
      <c n="getNOR" v="" />
      <c n="getNOT" v="" />
      <c n="getOWH" v="" />
      <c n="getPRS" v="" />
      <c n="getPST" v="" />
      <c n="getRDO" v="" />
      <c n="getRES" v="" />
      <c n="getRG1" v="" />
      <c n="getRG2" v="" />
      <c n="getRG3" v="" />
      <c n="getRPD" v="" />
      <c n="getRPW" v="" />
      <c n="getRTH" v="" />
      <c n="getRTI" v="" />
      <c n="getRTM" v="" />
      <c n="getSCR" v="" />
      <c n="getSIR" v="" />
      <c n="getSRE" v="" />
      <c n="getSS1" v="" />
      <c n="getSS2" v="" />
      <c n="getSS3" v="" />
      <c n="getSTA" v="" />
      <c n="getSV1" v="" />
      <c n="getSV2" v="" />
      <c n="getSV3" v="" />
      <c n="getTOR" v="" />
      <c n="getVS1" v="" />
      <c n="getVS2" v="" />
      <c n="getVS3" v="" />
      <c n="getWHU" v="" />
    </d>
  </sc>
  ```

## Getters and Setters

All known properties have 2-character names, e.g. XY or 3-character names, e.g. XYZ. The SYR Connect cloud can either call "getXYZ" to receive the property value during the next request, or it can call "setXYZ" with an appropriate value. Currently, most analysis focussed on the getters. In is currently unknown if for each getter also a setter is working. If setters have been found to work, they are listed in below tables.

### Basic Device data

This data is used to "register" the device in the SYR Connect cloud via GetBasicCommands.

| Property        | Example      | Unit   | Description
|-----------------|--------------|--------|-------------------------------------------------------
| getSRN          | "123456789"  |        | Serial number of the water softening unit. Used to identify the unit in the SYR Connect cloud
| getVER          | "1.7"        |        | Firmware version
| getTYP          | "80"         |        | Type of device (always 80?)
| getCNA          | "LEXplus10S" |        | Name of device. Known values: "LEXplus10", "LEXplus10S", "LEXplus10SL"

### Further Device data

Some further data about the device

| Property        | Example                          | Unit   | Description
|-----------------|----------------------------------|--------|-------------------------------------------------------
| getMAN          | "Syr"                            |        | Manufacturer
| getFIR          | "SLPS"                           |        | Firmware name. Used to find the correct firmware file during firmware update
| getCDE          | "010SCA19DF0917.01.024.1.1.0010" |        | *unknown constant (some kind of device identifier?)*
| getTMZ          | "01:00"                          |        | Timezone
| getDAT          | "1694635165"                     |        | Current time as UNIX timestamp (seconds since 1.1.1970)
| getLAN          | "1"                              |        | Language of the UI (0=English, 1=German, 3=Spanish)

### Device Status

| Property        | Example                          | Unit   | Description
|-----------------|----------------------------------|--------|-------------------------------------------------------
| getALM          | ""                               |        | Alarm code (e.g. `NoSalt`, `LowSalt`), a human readable message can be received via getSTA()
| getSTA          | "Bitte Salz nachfüllen"<br>"Płukanie wsteczne"<br>"Płukanie regenerantem"<br>"Płukanie wolne"<br>"Płukanie szybkie"<br>"Napełnianie"           |        | Status messages of the regeneration, in this case in German: "Please refill salt". Polish strings are not localized.

### Network

| Property        | Example               | Unit   | Description
|-----------------|-----------------------|--------|-------------------------------------------------------
| getMAC          | "01:23:45:67:89:AB"   |        | MAC address of the network port
| getIPA          | "123.123.123.1"       |        | IP-Adress
| getSNM          | "255.255.255.0"       |        | Subnet mask
| getDNS          | "123.123.123.254"     |        | DNS server
| getDGW          | "123.123.123.254"     |        | Default gateway
| getNET          | "po��czono"           |        | *unknown constant (some Polish text)*

### Holiday

Some devices seem to support setting holidays. The consequences for the water softening unit are unknown. For devices with leakage detection it makes the device more sensitive to consumed water. On the SYR Lex Plus 10 S Connect that was analysed the system automatically sets the holiday end to the current date.

| Property        | Example      | Unit   | Description
|-----------------|--------------|--------|-------------------------------------------------------
| getHSD          | "13"         |        | Holiday start day
| getHSM          | "9"          |        | Holiday start month
| getHSY          | "19"         |        | Holiday start **hour**
| getHED          | "13"         |        | Holiday end day
| getHEM          | "9"          |        | Holiday end month
| getHEY          | "2023"       |        | Holiday end **year**

### Settings

These settings can be set by the user.

| Property        | Example      | Unit      | Description
|-----------------|--------------|-----------|-------------------------------------------------------
| getIWH / setIWH | "14"         | °dH / °fH | Raw water hardness (of the untreated water)
| getOWH / setOWH | "7"          | °dh / °fH | Soft water hardness (that the treated water should have)
| getWHU / setWHU | "0"          |           | Water hardness unit: 0 = °dH, 1 = °fH
| getRDO / setRDO | "90"         | g/L       | Salt dosage
| getRTH / setRTH | "16"         | hour      | Regeneration time (hour)
| getRTM / setRTM | "0"          | minute    | Regeneration time (minute)
| getRPD / setRPD | "4"          | days      | Regeneration interval
| getRPW / setRPW | "0"          | bits      | Days on which regeneration is allowed stored as a bit mask (bit 0 = Mon .. bit 6 = Sun); mask `0` indicates no days configured.
| getRTY / setRTY | "0"          |           | 0 = Delayed regeneration, 1 = Immediate regeneration
| getCHG / setCHG | "0"          |           | Type of chlor generator: 0 = Chlor generator, 1 = Salt sensor, 2 = not available
| getPST / setPST | "1"          |           | Pressure sensor installed: 1 = not available, 2 = available
| getMPR / setMPR | "40"         | 1/10 bar  | The set water pressure
| getDWF / setDWF | "200"        | L         | Expected daily water consumption. If at the regeneration time getRES() < getDWF() a regeneration will start
| getFCO / setFCO | "0"          | ppm       | Iron content (always 0?)
| getCFO          | "0"          |           | Cycle flow offset, numeric counter

### Measurements

| Property                                              | Example            | Unit     | Description
|-------------------------------------------------------|--------------------|----------|-------------------------------------------------------
| getPRS                                                | "40"               | 1/10 bar | Measured water pressure if sensor is available (getPST() = 2), otherwise same as getMPR()<br>255 indicates an invalid values, e.g. when no pressure sensor is available but getPST() = 2
| getMXP                                                | "40"               | 1/10 bar | The maximum measured water pressure (reset at midnight)
| getMNP                                                | "40"               | 1/10 bar | The minimum measured water pressure (reset at midnight)
| getFLO                                                | "0"                | L/min    | Measured water flow
| getMXF                                                | "22"               | L/min    | Maximum flow within this hour
| getRES                                                | "1982"             | L        | Remaining capacity of water that can be treated
| getVOL                                                | "2000"             | L        | Total capacity
| getCS1<br>getCS2<br>getCS3                            | "63"<br>"0"<br>"0" | %        | Remaining capacity of the resin in tank 1, 2 or 3
| getSV1 / setSV1<br>getSV2 / setSV1<br>getSV3 / setSV1 | "7"<br>"0"<br>"0"  | kg       | Salt stored in tank 1, 2 or 3 (can also be set, e.g. on refill)
| getSS1<br>getSS2<br>getSS3                            | "1"<br>"0"<br>"0"  | weeks    | Salt in tank 1, 2 or 3 lasts for n weeks
| getPA1<br>getPA2<br>getPA3                            | "0"<br>"0"<br>"0"  |          | *unknown*
| getVS1<br>getVS2<br>getVS3                            | "0"<br>"0"<br>"0"  |          | *unknown*

### Regeneration

| Property                   | Example                 | Unit     | Description
|----------------------------|-------------------------|----------|-------------------------------------------------------
| getRG1<br>getRG2<br>getRG3 | "0"<br>"0"<br>"0"       |          | "1" if regeneration is running for tank 1, 2 or 3
| getCYN                     | "0"                     |          | Number of the running program
| getCYT                     | "00:00"                 |          | Duration of the running program
| getRTI                     | "00:00"                 |          | Total duration of the regeneration cylce
| getLAR                     | "1694501839"            |          | Last regeneration as UNIX timestamp (seconds since 1.1.1970)
| getTOR                     | "429"                   |          | Number of total regeneration cycles
| getNOR                     | "427"                   |          | Number of regeneration cycles in normal mode
| getSCR                     | "0"                     |          | *unknown, likely number of service regeneration cycles*
| getINR                     | "2"                     |          | Number of incomplete regeneration cycles
| setSIR                     | "1"                     |          | When set to "0" a regeneration is started immediately (e.g. SYR Connect Cloud uses this)

### Statistics

| Property        | Example                                                                                           | Unit   | Description
|-----------------|---------------------------------------------------------------------------------------------------|--------|--------------------------------------
| getMHF          | "8, 6, 115, 261, 251, 283, 136, 12, 20, 3, 16, 25, 31, 5, 0, 15, 40, 24, 21, 17, 3, 10, 323, 294" | L      | Hourly water consumption last Monday
| getUHF          | "57, 22, 121, 255, 257, 288, 171, 13, 1, 1, 3, 20, 18, 17, 12, 10, 6, 5, 5, 7, 22, 9, 76, 33"     | L      | Hourly water consumption last Tuesday
| getWHF          | "20, 0, 158, 272, 288, 33, 1, 4, 9, 7, 18, 6, 8, 17, 14, 0, 19, 9, 17, 16, 0, 0, 0, 0"            | L      | Hourly water consumption last Wednesday (in the example it is currently Wednesday, so they are for today; remaining hours are 0)
| getHHF          | "30, 1, 122, 254, 257, 144, 3, 15, 157, 147, 51, 24, 12, 3, 49, 8, 1, 23, 15, 2, 9, 23, 88, 42"   | L      | Hourly water consumption last Thursday
| getFHF          | "8, 1, 128, 256, 258, 143, 0, 12, 180, 168, 24, 14, 30, 11, 26, 7, 9, 14, 22, 3, 6, 33, 299, 296" | L      | Hourly water consumption last Friday
| getSHF          | "0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 20, 0, 0, 0, 0, 0, 12, 12, 33, 71, 28"                    | L      | Hourly water consumption last Saturday
| getNHF          | "7, 15, 124, 255, 260, 285, 137, 34, 3, 18, 0, 0, 0, 42, 6, 30, 2, 8, 9, 11, 10, 0, 1, 43"        | L      | Hourly water consumption last Sunday
| getTOF          | "916"                                                                                             | L      | Water consumption today (continuously updated)
| getYEF          | "1429"                                                                                            | L      | Water consumption yesterday
| getCWF          | "4265"                                                                                            | L      | Water consumption this week (continuously updated)
| getLWF          | "11056"                                                                                           | L      | Water consumption last week
| getCMF          | "19751"                                                                                           | L      | Water consumption this month (continuously updated)
| getLMF          | "37998"                                                                                           | L      | Water consumption last month
| getCOF          | "583939"                                                                                          | L      | Cumulated water consumption in the past (continuously updated)<br>In theory this should reflect the numbers on your water metering device but the precision seems to be low.

### Leakage protection

These properties are only available on devices that contain leakage protection, e.g. LEX Plus 10 SL Connect.

| Property        | Example      | Unit    | Description
|-----------------|--------------|---------|-------------------------------------------------------
| getAB / setAB   | "1"          |         | Valve shut-off: 1 = open, 2 = closed
| getVLV          | "20"         |         | Valve status: 10 = closed, 11 = closing, 20 = open, 21 = opening
| getLE / setLE   | "4"          |         | Leakage volume when present: 1 = ?L, 2 = 100L, 3=150L, 3 = 200L
| getT1 / setT1   | "1"          |         | Leakage time (when present?): 1 = 0.5h, 2 = 1.0h, 3 = 1.5h, ..., 50 = 25.0h
| getT2 / setT2   | "1"          |         | Leakage time (when present?): 1 = ?L, 2 = 1h, 3 = 1.5h, 4 = 2h
| getTMP / setTMP | "0"          | seconds | Deactivate leakage protection for n seconds
| getUL / setUL   | "0"          |         | User profile Leakage protection mode: 0 = present, 1 = absent
| getCEL          | "203"        | 1/10 °C | Water temperature, e.g. 203 = 20.3°C
| getNPS          | "22"         |         | Microleakage count
| getPF1<br>getPF2<br>getPF3<br>getPF4<br>getPF5<br>getPF6<br>getPF7<br>getPF8 | "0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0" | L/h | Leak protection flow rate 1-8
| getPT1<br>getPT2<br>getPT3<br>getPT4<br>getPT5<br>getPT6<br>getPT7<br>getPT8 | "0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0" | minutes | Leak protection time 1-8
| getPV1<br>getPV2<br>getPV3<br>getPV4<br>getPV5<br>getPV6<br>getPV7<br>getPV8 | "0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0"<br>"0" | L | Leak protection volume 1-8

### Unknown leakage protection

These properties are only available on devices that contain leakage protection, e.g. LEX Plus 10 SL Connect.

| Property        | Example      | Unit   | Description
|-----------------|--------------|--------|-------------------------------------------------------
| getDMA          | "1"          |        | *unknown*
| getAVO          | "0mL"        |        | *unknown*
| getBSA          | "0"          |        | *unknown*
| getDBD          | "10"         |        | *unknown*
| getDBT          | "15"         |        | *unknown*
| getDST          | "180"        |        | *unknown*
| getDCM          | "3"          |        | *unknown*
| getDOM          | "60"         |        | *unknown*
| getDPL          | "10"         |        | *unknown*
| getDTC          | "3"          |        | *unknown*
| getDRP          | "1"          |        | *unknown*
| getALA          | "0"          |        | *unknown*
| getTN           | "20"         |        | *unknown*
| getSMR          | "1"          |        | *unknown*
| getSRE          | "0"          |        | *unknown*
| getVAC          | "0"          |        | *unknown*
| getVAT          | "3"          |        | *unknown*

### Unknown statistics

| Property        | Example      | Unit   | Description
|-----------------|--------------|--------|-------------------------------------------------------
| getTUF          | "1752"       |        | Somewhat related to water consumption. Updated on day change Monday -> Tuesday
| getWEF          | "997"        |        | Somewhat related to water consumption. Updated on day change Tuesday -> Wednesday
| getTHF          | "1212"       |        | Somewhat related to water consumption. Updated on day change Wednesday -> Thursday
| getFRF          | "1077"       |        | Somewhat related to water consumption. Updated on day change Thursday -> Friday
| getSAF          | "1492"       |        | Somewhat related to water consumption. Updated on day change Friday -> Saturday
| getSUF          | "1168"       |        | Somewhat related to water consumption. Updated on day change Saturday -> Sunday **and** Sunday -> Monday (seems to be a bug)
| getTFO          | "9508"       |        | *unknown*
| getUWF          | "15599"      |        | *unknown*

### Unknown

| Property        | Example      | Unit   | Description
|-----------------|--------------|--------|-------------------------------------------------------
| getBTM          | "1"          |        | *unknown constant?*
| getBTS          | "0"          |        | *unknown constant?*
| getCOR          | "30"         |        | *unknown constant?*
| getDEN          | "1"          |        | *unknown constant?*
| getDHC          | "0"          |        | *unknown constant?*
| getFWM          | "1"          |        | *unknown constant?*
| getFWS          | "0"          |        | *unknown constant?*
| getHOT          | "50"         |        | *unknown constant?*
| getIPH          | ""           |        | *unknown constant?*
| getLGO          | "1"          |        | *unknown constant?*
| getMOF          | "0"          |        | *unknown constant?*
| getNOT          | ""           |        | *unknown constant?*
| getREV          | "10"         |        | *unknown constant?*
| getRPE          | "30"         |        | *unknown constant?*
| getSDR          | "1"          |        | *unknown constant?*
| getSMR          | "1"          |        | *unknown constant?*
| getSRE          | "0"          |        | *unknown constant?*
| getVAC          | "0"          |        | *unknown constant?*
| getVAT          | "3"          |        | *unknown constant?*

## Further information

- SYR Connect Protocol
  <https://github.com/Richard-Schaller/syrlex2mqtt/blob/main/doc/syrconnect-protocol.md>
- Brief description of the Webservices offered by SYR Connect:  
  <http://syrconnect.de/WebServices/SyrConnectLimexWebService.asmx>
- Githup repository of a project that simulates the SYR Connect cloud for usage in iobroker (German):  
  <https://github.com/eifel-tech/ioBroker.syrconnect>
- Analysis of the network traffic of a SYR LexPlus 10 with the SYR Connect cloud:  
  <https://www.msxfaq.de/sonst/iot/syr_lexplus_10.htm> (German)
- Analysis of the network traffic of a Syr Safe-T Connect with the SYR Connect cloud:  
  <https://www.msxfaq.de/sonst/iot/syr_safe-t_connect.htm> (German)
