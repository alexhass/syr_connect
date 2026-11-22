<!-- markdownlint-disable-next-line MD041 -->
<img src="custom_components/syr_connect/brand/logo.png" alt="Syr" width="200">

# SYR Connect - Integración para Home Assistant

[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![syr_connect installs](https://img.shields.io/badge/dynamic/json?logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.syr_connect.total)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)
[![Quality scale: Platinum](https://img.shields.io/badge/Quality%20scale-Platinum%20%F0%9F%8F%86-b5d2e0?style=flat)](https://github.com/alexhass/syr_connect/blob/main/quality_scale.yaml)

<!-- ha-marketplace:exclude-start -->

[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

<!-- ha-marketplace:exclude-end -->

Esta integración personalizada permite controlar los dispositivos SYR Connect desde Home Assistant. También puede utilizarse con dispositivos idénticos de otras marcas. Las instalaciones mixtas de distintas marcas también son compatibles.

| Marca | Enlace |
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

## Capturas de pantalla

Ejemplos de la interfaz de los dispositivos:

![Captura de pantalla de LEXplus10S](docs/assets/screenshots/en/lexplus10s.png)

![Captura de pantalla de Safe-T+](docs/assets/screenshots/en/safetplus.png)

<!-- ha-marketplace:exclude-start -->

## Instalación

[![Abrir la instancia de Home Assistant y abrir un repositorio en el Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=alexhass&repository=syr_connect&category=integration)

### Marketplace (recomendado)

1. Ir a Ajustes > Marketplace.
2. Buscar "SYR Connect".
3. Hacer clic en "Instalar".
4. Reiniciar Home Assistant.

### Instalación manual

1. Copiar la carpeta `syr_connect` en el directorio `custom_components`.
2. Reiniciar Home Assistant.

<!-- ha-marketplace:exclude-end -->

## Configuración

[![Abrir la instancia de Home Assistant y empezar a configurar una nueva integración.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)

La integración admite dos modos de configuración:

### Configuración con la API en la nube (todos los dispositivos)

1. Ir a Ajustes > Dispositivos y servicios.
2. Hacer clic en "+ Añadir integración".
3. Buscar "SYR Connect".
4. Seleccionar "Nube".
5. Introducir las credenciales de la aplicación móvil:
   - **Servicio**: La aplicación en la que están configurados los dispositivos
   - **Nombre de usuario**: Nombre de usuario de la cuenta en esta aplicación
   - **Contraseña**: Contraseña de la cuenta en esta aplicación

### Configuración con la API local (solo dispositivos más recientes)

Para dispositivos más recientes con una API JSON local, por ejemplo los dispositivos NeoSoft y Trio, SafeTech Lock, TRIO Lock, AC 3200 y RSA Connect, así como sus dispositivos idénticos de otras marcas. La selección de modelo durante la configuración muestra todos los modelos compatibles:

1. Ir a Ajustes > Dispositivos y servicios.
2. Hacer clic en "+ Añadir integración".
3. Buscar "SYR Connect".
4. Seleccionar "Local".
5. Introducir los datos del dispositivo:
   - **Modelo del dispositivo**: Modelo del dispositivo (p. ej., NeoSoft 2500 Connect)
   - **Nombre de host o dirección IP**: Dirección IP o nombre de host del dispositivo (p. ej., `192.168.178.199`)

**Nota**: La dirección IP del dispositivo aparece en la lista de clientes DHCP del router o en el menú de la pantalla del dispositivo.

**Importante**: Para un funcionamiento estable, el dispositivo debe tener una **dirección IP estática** o una **concesión DHCP reservada** (reserva DHCP). Si cambia la dirección IP del dispositivo, la integración pierde la conexión. La nueva dirección se introduce con "Reconfigurar" en el menú de tres puntos (⋮) de la entrada. La entrada queda vinculada a su dispositivo mediante el número de serie: otro dispositivo en la nueva dirección se rechaza y debe añadirse como una nueva entrada. Como alternativa, puede utilizarse un nombre de host si la red admite la resolución DNS local.

## Funciones

La integración crea automáticamente entidades para todos los dispositivos SYR Connect de la cuenta.

### Dispositivos compatibles

Esta integración funciona con los descalcificadores y los dispositivos de detección de fugas de SYR y con otros dispositivos que aparecen en la nube SYR Connect (a través de la aplicación móvil correspondiente).

Probados y con funcionamiento confirmado:

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

Otros dispositivos también son de interés, pero puede que haya que integrarlos o al menos probarlos (se agradecen los informes):

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
- POLYGONVATRO SafeTech Connect (vendido con el seguro de hogar de AXA como "Wasserwächter")
- RWC MultiSafe Floor Leak Sensor
- RWC MultiSafe Leak Detector Control Valve
- Sanibel Automatic Backwash System RSA A25
- Sanibel Softwater DUO A25
- SYR AC 3200 Connect
- SYR AC All-in-One 3228 Connect
- SYR CONTROLICmini
- SYR HVA
- SYR HygBox Connect
- SYR Hygiene Module (fría / caliente / fría y caliente)
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

**Nota**: Si un dispositivo es visible en la cuenta de SYR Connect, la integración lo detecta y crea las entidades automáticamente. Para un "dispositivo no probado", compartir los diagnósticos ayuda a encontrar valores desconocidos y a comprobar que todo funciona según lo previsto. Así también se puede ampliar la lista de dispositivos probados.

### Dispositivos no compatibles

- Dispositivos SYR Oceanic Limex SMART COMPACT/MINI/MAXI. Estos dispositivos utilizan otro portal en la nube (`i-lexconnect.com`) en lugar del servicio en la nube SYR Connect. Son dispositivos Husty SaoCal con otra marca.
- Dispositivos Husty SaoCal. Véase [husty_integration_home_assistant](https://github.com/trafopowielacz/husty_integration_home_assistant).

### Funcionalidad compatible

#### Sensores

La integración ofrece una supervisión completa de los dispositivos:

#### Calidad del agua y capacidad

- Supervisión de la dureza del agua cruda y blanda
- Conductividad del agua (µS/cm)
- Rango de dureza del agua (blanda, media, dura), estimado a partir de la conductividad (familia SafeTech)
- Factor de conductividad
- Temperatura del agua (°C)
- Seguimiento de la capacidad de descalcificación restante
- Capacidad de resina por depósito (hasta 3 depósitos, %)
- Supervisión del volumen total
- Indicación de la unidad de dureza del agua

#### Información de regeneración

- Estado de regeneración e indicador del depósito activo (hasta 3 depósitos)
- Modo de regeneración (Estándar / ECO / Power / Automático)
- Número de regeneraciones realizadas
- Fecha y hora de la última regeneración
- Ajustes del intervalo de regeneración
- Horario de regeneración
- Contadores de ciclos y tiempos

#### Gestión de la sal

- Cantidad de sal en los depósitos (1–3)
- Reserva de sal (semanas restantes)
- Capacidad de reserva de resina por botella

#### Supervisión del sistema

- Supervisión de la presión del agua
- Caudal (actual e instantáneo)
- Contador de caudal (consumo total)
- Tensión de la batería y de la red
- Estado de alarmas, notificaciones y advertencias (código actual y las últimas 8 entradas del historial)

#### Protección contra fugas (LEXplus10SL / Trio DFR/LS)

- Límites de volumen y duración de la protección contra fugas (perfiles de presencia y de ausencia)
- Índice del perfil de protección contra fugas activo
- Perfiles de protección contra fugas 1–8 (límite de volumen, duración máxima, umbral de caudal, indicadores de advertencia y de zumbador)
- Temporizador de desactivación temporal
- Umbral de advertencia de fuga (%)

#### Prueba de microfugas (Trio DFR/LS, SafeTech, SafeTech+, TRIO Lock, SafeTech Lock)

- Intervalo y estado de la prueba de microfugas
- Duración de la prueba y número de eventos

#### Fase de autoaprendizaje (Trio DFR/LS, SafeTech+, TRIO Lock, SafeTech Lock)

- Tiempo de autoaprendizaje restante y transcurrido
- Caudal y volumen acumulado durante el autoaprendizaje
- Ajustes del autoaprendizaje: margen de volumen y tiempo, margen de caudal, caudal mínimo

#### Sensor de suelo (SafeFloor)

- Humedad y temperatura actuales
- Nivel de batería (%)
- Estado de alarma

#### Filtro y retrolavado

- Tipo de filtro (SafeTech, SafeTech Lock, TRIO Lock, AC All-in-One 3228 Connect)
- Contenido de hierro (familia LEX)
- Contadores de retrolavados automáticos y manuales (retrolavado automático RSA)

#### Mantenimiento

- Próximas fechas de mantenimiento (semestral y anual)
- Consumo diario de agua previsto

#### Información del dispositivo

- Número de serie
- Versión de firmware y modelo
- Tipo de dispositivo y fabricante
- Información de red (IP, MAC, puerta de enlace)
- Estado de la conexión Wi-Fi e intensidad de la señal
- Zona horaria (desfase UTC)

#### Sensores binarios

- **Zumbador en alarma**: Indica si el zumbador suena en caso de alarma.
- **Protección contra fugas**: Indica si la protección contra fugas está activa o desactivada.
- **Prueba de válvula**: Indica si se está realizando una prueba de válvula.
- **Comprobación de firmware**: Indica si hay un firmware nuevo disponible (se comprueba al iniciar y cada 6 horas).
- **Horario de verano**: Indica si el dispositivo cambia automáticamente al horario de verano.
- **Sensor de temperatura**, **Sensor de presión**, **Sensor de conductividad**: Indican si el sensor de medición está activo o desactivado.
- **Supervisión del sensor de suelo**: Indica si la supervisión de los sensores de suelo está activada.

#### Botones (acciones)

- **Regenerar ahora**: Iniciar una regeneración inmediata.
- **Restablecer alarma**: Borrar los mensajes de alarma activos.
- **Restablecer notificación**: Borrar los mensajes de notificación.
- **Restablecer advertencia**: Borrar los mensajes de advertencia.
- **Iniciar prueba de microfugas**: Iniciar la prueba de microfugas. La válvula permanece cerrada unos 4 minutos, y tomar agua durante la prueba da un resultado negativo (solo API local).
- **Purga manual (agua fría)**, **Purga manual (agua caliente)**: Iniciar una purga manual de la tubería de agua (módulo de higiene).

#### Interruptores

- **Zumbador en alarma**: Activar o desactivar el zumbador en caso de alarma.
- **Permitir cambio de perfil en el dispositivo**: Permitir o bloquear el cambio del perfil de protección contra fugas con el botón del dispositivo.
- **Modo de llenado**: Activar o desactivar el llenado automático (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect y sus dispositivos idénticos de otras marcas, All-in-One+).
- **Llenado inicial**: Iniciar o detener el llenado inicial (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect y sus dispositivos idénticos de otras marcas, All-in-One+).
- **Llenado manual**: Iniciar o detener el llenado manual (All-in-One+).
- **Retrolavado automático**: Activar o desactivar el retrolavado automático (retrolavado automático RSA).
- **Recordatorio de retrolavado**: Activar o desactivar el recordatorio de retrolavado (retrolavado automático RSA).
- **Purga por estancamiento**, **Purga por temperatura**, **Purga periódica**: Activar o desactivar las tres funciones de purga (HygBox).

#### Selectores (configuración)

- **Hora de regeneración**: Ajustar la hora diaria de regeneración (intervalos de 15 minutos).
- **Perfil de protección contra fugas activo**: Seleccionar el perfil de protección contra fugas activo (en dispositivos con varios perfiles).
- **Cantidad de sal en el depósito 1–3**: Ajustar la cantidad de sal por depósito (según el modelo, hasta 3 depósitos).
- **Intervalo de regeneración**: Ajustar la frecuencia de la regeneración (según el modelo: hasta 3, 4 o 99 días).
- **Orientación de la pantalla**: Ajustar la orientación de la pantalla (0 / 90 / 180 / 270 grados, en dispositivos con pantalla).
- **Idioma del dispositivo**: Ajustar el idioma de la pantalla del dispositivo: alemán, inglés, español, italiano o polaco (SafeTech).
- **Modo de regeneración**: Seleccionar Estándar / ECO / Power / Automático (en los dispositivos que lo admiten).
- **Dureza del agua cruda**, **Dureza del agua blanda**: Ajustar la dureza del agua cruda y del agua descalcificada (familia LEX, CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect y sus dispositivos idénticos de otras marcas, All-in-One+). La unidad sigue la unidad de dureza configurada en el dispositivo (°dH, °fH, °e, mg/l CaCO₃, ppm, mmol/l o mval/l).
- **Tratamiento del agua y llenado** (CLEAR PRO FILL All-in-One, AC All-in-One 3228 Connect, AC 3200 Connect y sus dispositivos idénticos de otras marcas, All-in-One+): Tamaño y tipo de cartucho, dureza del agua blanda o conductividad máxima de salida (según el cartucho), periodo de llenado, número de ciclos de llenado, duración y cantidad máximas de llenado, presión objetivo, umbral de advertencia de capacidad restante, volumen y duración máximos del llenado inicial.
- **Sensor de suelo** (SafeFloor): Duración de la alarma, umbrales mínimo y máximo de humedad y temperatura ("Apagado" desactiva un umbral), intervalo de medición e intervalo de sincronización de los ajustes.
- **Purga de higiene** (HygBox): Tipo de agua, tiempo de estancamiento y volumen de purga, temperatura de inicio y de parada, duración máxima de la purga y purgas por día, intervalo y volumen de la purga periódica, intervalo de sincronización de los ajustes.
- **Purga de higiene** (módulo de higiene, Safe-T Hygiene Module): Tiempo de estancamiento, intervalo de purga, límite de temperatura, duración máxima y volumen máximo de purga de la tubería de agua fría y de la de agua caliente.
- **Dosificación** (NeoDos Connect): Tamaño del bidón, líquido de dosificación y modo de funcionamiento.
- **Retrolavado** (retrolavado automático RSA): Intervalo de retrolavado e intervalo de recordatorio de retrolavado (1–365 días).
- **Protección contra fugas** (Safe-T+): Nivel de protección contra fugas en presencia y en ausencia (un nivel en ausencia activa el perfil de ausencia, «Apagado» vuelve al perfil de presencia), fuga de tiempo y desactivación temporal de la protección contra fugas.

#### Control de la válvula

- **Cierre de válvula**: Controlar la válvula principal de corte de agua.
  - Abrir y cerrar la válvula.
  - Supervisar la posición y el estado actuales de la válvula.
  - Integración con automatizaciones de detección de fugas para el cierre automático.

#### Actualización de firmware

- **Actualización de firmware**: Indica si hay un firmware nuevo disponible y lo instala. El dispositivo debe estar conectado a Internet. El dispositivo no informa del número de la nueva versión.

### Modos de API

La integración admite dos modos de API:

#### API en la nube (basada en XML)

- **Compatible con**: Todos los dispositivos SYR Connect
- **Conexión**: A través del servicio en la nube SYR Connect
- **Autenticación**: Nombre de usuario y contraseña de la cuenta de SYR Connect
- **Ventajas**: Funciona con todos los modelos de dispositivo, acceso remoto desde cualquier lugar
- **Requisitos**: Conexión a Internet, cuenta de SYR Connect

#### API local (basada en JSON)

- **Compatible con**: Modelos más recientes con una API local integrada, por ejemplo NeoSoft, Trio DFR/LS, TRIO Lock, SafeTech Lock, AC 3200, RSA, Pontos Base, All-in-One+, HygBox y variantes más recientes de SafeTech, también de otras marcas. La selección de modelo durante la configuración muestra todos los modelos compatibles.
- **Conexión**: Directa con el dispositivo a través de la red local (puerto 5333).
- **Autenticación**: No se necesitan credenciales.
- **Ventajas**: Sin dependencia de Internet, tiempos de respuesta más rápidos, sin límites de peticiones de la nube.
- **Requisitos**: El dispositivo debe estar en la misma red que Home Assistant y necesita una dirección IP estática o un nombre de host.

El modo de API se elige durante la configuración (Nube o Local).

## Cómo se actualizan los datos

La integración consulta la API del dispositivo a intervalos regulares (por defecto: 60 segundos). El proceso de actualización depende del modo de API:

### Proceso de actualización con la API en la nube

1. **Inicio de sesión**: Se autentica en la API en la nube de SYR Connect con las credenciales.
2. **Detección de dispositivos**: Obtiene todos los proyectos y dispositivos asociados a la cuenta, al inicio y después cada 30 minutos. Un dispositivo eliminado de la cuenta se elimina de Home Assistant junto con sus entidades.
3. **Actualizaciones de estado**: Para cada dispositivo, obtiene el estado actual con todos los valores de los sensores.
4. **Actualizaciones de entidades**: Actualiza todas las entidades de Home Assistant con los valores más recientes.

### Proceso de actualización con la API local

1. **Actualizaciones de estado**: Obtiene el estado del dispositivo directamente del punto de acceso local.
2. **Actualizaciones de entidades**: Actualiza todas las entidades de Home Assistant con los valores más recientes.

La API local es más rápida y no depende de la conexión a Internet, por lo que es más fiable para la supervisión en tiempo real y las automatizaciones.

Si una actualización falla temporalmente (p. ej., tiempo de espera agotado, mantenimiento de la nube o una respuesta incompleta), las entidades conservan sus últimos valores y el error se escribe en el registro. Las entidades solo dejan de estar disponibles cuando la nube informa de que el dispositivo está desconectado. Permanecen no disponibles hasta que el dispositivo vuelve a enviar un estado completo.

Mientras no se puedan obtener datos en absoluto, la integración realiza consultas con menos frecuencia: el intervalo se duplica tras cada actualización fallida, hasta 15 minutos. La primera actualización correcta restablece el intervalo configurado.

Si no se pueden obtener datos durante más de 1 hora, el fallo ya no se trata como temporal: las entidades afectadas dejan de estar disponibles y se muestra un mensaje en **Ajustes** → **Reparaciones**. Ambos desaparecen en cuanto se vuelven a obtener datos.

### Historial de mediciones de SafeFloor

Un SafeFloor mide la temperatura y la humedad con regularidad, pero envía sus mediciones a la nube solo cada pocos días, por lo que sus sensores muestran una línea plana seguida de un salto. La integración obtiene las mediciones individuales de la nube cada 12 horas y las guarda como estadísticas con el nombre de los sensores (p. ej., "Lavadero Temperatura"). Para ver la curva real, se añade una tarjeta a un panel:

1. Abrir el panel y seleccionar **Editar panel** arriba a la derecha.
2. Seleccionar **Añadir tarjeta**, escribir `Statistics` en **Buscar tarjetas** y elegir **Gráfico de estadísticas**.
3. Seleccionar **Mostrar editor de código**, sustituir el texto por uno de los fragmentos siguientes y seleccionar **Guardar**.
4. Seleccionar **Hecho**.

`123456789` se sustituye por el número de serie del SafeFloor. Se necesita una tarjeta por medición.

Temperatura:

```yaml
type: statistics-graph
title: Temperatura
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_getcel_history
```

Humedad:

```yaml
type: statistics-graph
title: Humedad
chart_type: line
period: hour
days_to_show: 14
stat_types:
  - mean
entities:
  - syr_connect:123456789_gethmd_history
```

La nube solo conserva las mediciones de los últimos 6 días. El intervalo de sincronización del sensor debe ser de 6 días o menos; de lo contrario, se pierden mediciones. Las estadísticas se eliminan junto con el dispositivo.

### Limitaciones conocidas

- **Dependencia de la nube**: La API en la nube requiere una conexión a Internet activa y un servicio en la nube operativo.
- **Intervalo de actualización**: La API en la nube permite un intervalo de actualización de al menos 60 segundos, la API local de al menos 10 segundos.
- **Acceso de escritura limitado**: Se admiten cambios de configuración (hora de regeneración, cantidades de sal, intervalos) y acciones de control (regeneración, control de la válvula), pero algunos ajustes avanzados solo pueden estar disponibles en la aplicación SYR Connect.
- **Compatibilidad con la API local**: No todos los modelos ofrecen una API JSON local. LEX 1500, LEXplus, i-LEX, Safe-T, SafeFloor, HVA, los módulos de higiene y las variantes más antiguas de SafeTech requieren el acceso mediante la API en la nube.

## Casos de uso y ejemplos

### Ejemplos de automatizaciones

Los ejemplos utilizan la sintaxis YAML de `configuration.yaml`. En todos los ejemplos, `<serial_number>` se sustituye por el número de serie del dispositivo y `<device_name>` por el nombre del dispositivo de la aplicación móvil en Home Assistant.

#### Aviso de sal baja

Notificación cuando la reserva de sal se está agotando:

```yaml
automation:
  - alias: "SYR: Aviso de sal baja"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Quedan menos de 2 semanas de sal
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Descalcificador"
          message: "Reserva de sal baja: quedan menos de 2 semanas"
```

#### Informe diario de regeneración

Resumen diario de las regeneraciones, la capacidad restante y la reserva de sal:

```yaml
automation:
  - alias: "SYR: Informe diario de regeneración"
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Informe diario del descalcificador"
          message: >
            Regeneraciones (total): {{ states('sensor.syr_connect_<serial_number>_getnor') }}
            Capacidad restante: {{ states('sensor.syr_connect_<serial_number>_getres') }} L
            Reserva de sal: {{ states('sensor.syr_connect_<serial_number>_getss1') }} semanas
```

#### Notificación de alarma

Notificación inmediata cuando el dispositivo informa de una alarma:

```yaml
automation:
  - alias: "SYR: Notificación de alarma"
    triggers:
      - trigger: template
        value_template: >
          {{ states('sensor.syr_connect_<serial_number>_getala')
             not in ['no_alarm', 'unknown', 'unavailable'] }}
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "⚠️ Alarma SYR"
          message: "Alarma actual: {{ states('sensor.syr_connect_<serial_number>_getala') }}"
          data:
            priority: high
```

#### Supervisión del caudal de agua

Aviso de un caudal de agua anormalmente alto durante varios minutos (posible fuga):

```yaml
automation:
  - alias: "SYR: Aviso de caudal alto"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 1200  # Caudal superior a 1200 l/h (20 l/min)
        for:
          minutes: 5
    actions:
      - action: notify.mobile_app_<device_name>
        data:
          title: "Caudal de agua alto detectado"
          message: "Caudal de agua inusual: posible fuga"
```

#### Sensor de fugas: cerrar la válvula de agua

Cierra la válvula de corte de agua de SYR con la acción estándar `valve.close` cuando un sensor de fugas detecta agua. Los ID de entidad se sustituyen por los utilizados en la instalación. Esta automatización puede convertirse en una acción de seguridad crítica, por lo que debe probarse con mucho cuidado.

```yaml
automation:
  - alias: "SYR: Cerrar la válvula en caso de fuga"
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
          title: "SYR: Fuga detectada, válvula cerrada"
          message: "Se ha detectado una fuga de agua: la válvula de corte de agua de SYR se ha cerrado automáticamente."
```

#### Regeneración en fin de semana

Inicia una regeneración los sábados y domingos a las 03:00:

```yaml
automation:
  - alias: "SYR: Regeneración en fin de semana"
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

## Opciones de configuración

### Intervalo de actualización

Los datos se actualizan cada 60 segundos de forma predeterminada. El intervalo se ajusta en las opciones de la integración: al menos 60 segundos para la nube, al menos 10 segundos para los dispositivos locales y como máximo 600 segundos en ambos casos.

1. Abrir Ajustes > Dispositivos y servicios.
2. Abrir la integración SYR Connect.
3. Seleccionar "Configurar".
4. Ajustar el intervalo de actualización (en segundos).

## Eliminación

Para eliminar la integración de Home Assistant:

1. Ir a Ajustes > Dispositivos y servicios.
2. Buscar la integración SYR Connect.
3. Hacer clic en el menú de tres puntos (⋮).
4. Seleccionar "Eliminar".
5. Confirmar la eliminación.

Todos los dispositivos y entidades asociados se eliminan automáticamente.

## Solución de problemas

### Descargar los diagnósticos

En caso de problemas, los diagnósticos de la entrada de la integración son de ayuda. Contienen los datos de todos los dispositivos de la entrada:

1. Abrir Ajustes > Dispositivos y servicios.
2. Abrir la integración SYR Connect.
3. Abrir el menú de tres puntos (⋮) de la entrada (cuenta o dispositivo local).
4. Seleccionar "Descargar diagnósticos".

Las contraseñas, los nombres de usuario, los datos de sesión, el número de código del dispositivo, las direcciones IP, las puertas de enlace y el nombre de la red Wi-Fi se eliminan del archivo, y el número de serie se enmascara.

### Registros de depuración

La activación y desactivación del registro de depuración se describe en [docs/howto-debugging.md](docs/howto-debugging.md) (en inglés).

### La conexión falla

- **Comprobar las credenciales**: Verificar el nombre de usuario y la contraseña de la aplicación SYR Connect.
- **Probar la aplicación**: El inicio de sesión en la aplicación móvil SYR Connect debe funcionar con la misma cuenta.
- **Revisar los registros**: Ir a Ajustes > Sistema > Registros y buscar errores de "syr_connect".
- **Problemas de red**: Home Assistant debe tener acceso a Internet.

### Errores de autenticación

Para errores de "Authentication failed":

1. Verificar las credenciales.
2. La integración solicitará una nueva autenticación.
3. Ir a Ajustes > Dispositivos y servicios.
4. Hacer clic en "Autenticar" en la integración SYR Connect.
5. Volver a introducir las credenciales.

La nueva autenticación y "Reconfigurar" solo cambian la contraseña de la cuenta. Otro nombre de usuario es otra cuenta: se rechaza allí y debe añadirse como una nueva entrada.

### No se encuentran dispositivos

- **Configuración de la aplicación**: Los dispositivos deben estar correctamente configurados en la aplicación SYR Connect.
- **Acceso a la cuenta**: La cuenta debe ser aquella en la que están configurados los dispositivos.
- **Estado de los dispositivos**: Comprobar si los dispositivos están en línea en la aplicación SYR Connect.
- **Registros**: Revisar los registros de Home Assistant en busca de mensajes de error concretos.

### Las entidades aparecen como no disponibles

- **Dispositivo desconectado**: La nube informa de que el dispositivo está desconectado. Deben comprobarse la alimentación eléctrica y la conexión de red del dispositivo.
- **Aplicación SYR Connect**: El dispositivo debe aparecer como en línea en la aplicación SYR Connect.
- **De nuevo en línea**: Las entidades vuelven a estar disponibles en cuanto el dispositivo envía un estado completo.

- **Sin conexión durante más de 1 hora**: No se han podido obtener datos de la nube o del dispositivo durante más de 1 hora. Se muestra un mensaje en **Ajustes** → **Reparaciones**. Deben comprobarse la conexión a Internet y el estado de la nube SYR Connect.
- **Problema de red**: Si no se ha podido resolver el nombre de host o no se ha podido abrir ninguna conexión, el mensaje indica la red como causa. Deben comprobarse la conexión de red y los ajustes de DNS de Home Assistant y, en un dispositivo local, también su dirección IP.

Los problemas temporales con la conexión o con el servicio en la nube no hacen que las entidades dejen de estar disponibles. Las entidades conservan sus últimos valores y el error se escribe en el registro.

### Uso elevado de CPU o memoria

- **Aumentar el intervalo de actualización**: Ajustar un valor más alto (p. ej., 120–300 segundos) en las opciones de la integración.
- Esto reduce las llamadas a la API y la carga del sistema.

<!-- ha-marketplace:exclude-start -->

## Dependencias

La integración requiere los siguientes paquetes de Python:

- `pycryptodomex>=3.19.0,<4.0`: Para el cifrado y descifrado AES
- `defusedxml>=0.7.1,<1.0`: Para el análisis seguro de XML (evita ataques XXE)

**Nota**: La integración utiliza `defusedxml` para el análisis seguro de XML y `pycryptodomex` (no `pycryptodome`) para evitar conflictos con las bibliotecas criptográficas integradas en Home Assistant.

Home Assistant instala los paquetes **automáticamente** cuando:

1. Se añade la integración a través de la interfaz de usuario.
2. Se reinicia Home Assistant después de la instalación.

Los requisitos detallados del sistema y la solución de problemas se encuentran en [REQUIREMENTS.md](REQUIREMENTS.md) (en inglés).

<!-- ha-marketplace:exclude-end -->

## Aviso legal

### IMPORTANTE: Leer antes de utilizar la integración

Esta integración controla sistemas de tratamiento de agua y de corte de agua. Una configuración incorrecta o automatizaciones defectuosas pueden provocar daños por agua, fallos del sistema o daños materiales.

- **Uso bajo la propia responsabilidad**: Este software se proporciona "tal cual", sin garantía de ningún tipo.
- **Pruebas exhaustivas**: Las automatizaciones deben probarse siempre en condiciones seguras antes de ponerlas en funcionamiento.
- **Sistemas críticos**: Las automatizaciones de control de la válvula pueden cortar todo el suministro de agua y deben probarse con cuidado.
- **Sin responsabilidad**: Los autores y colaboradores no se hacen responsables de ningún daño, daño por agua, daño material u otros problemas derivados del uso de esta integración.
- **Dependencia de la nube**: Esta integración depende del servicio en la nube SYR Connect, cuya disponibilidad no está garantizada.
- **Plan alternativo**: Debe existir un acceso alternativo a la válvula de corte de agua en caso de fallo del sistema.

La instalación y el uso de esta integración implican reconocer estos riesgos y aceptar utilizarla de forma responsable.

## Licencia

Apache License 2.0, véase [LICENSE](LICENSE)

## Créditos

- Inspirado en el adaptador [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) de TA2k.
- Muchas gracias al equipo SYR IoT-Development-Team por compartir los logotipos.
