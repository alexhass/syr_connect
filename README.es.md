![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)

# SYR Connect - Integración Home Assistant

![Syr](custom_components/syr_connect/logo.png)

Esta integración personalizada permite controlar dispositivos SYR Connect desde Home Assistant.

## Instalación

### HACS (recomendado)

1. Abre HACS en Home Assistant
2. Ve a "Integraciones"
3. Haz clic en los tres puntos arriba a la derecha
4. Selecciona "Custom repositories"
5. Añade la URL del repositorio
6. Selecciona la categoría "Integration"
7. Haz clic en "Add"
8. Busca "SYR Connect" e instálalo
9. Reinicia Home Assistant

### Instalación manual

1. Copia la carpeta `syr_connect` en tu carpeta `custom_components`
2. Reinicia Home Assistant

## Configuración

1. Ve a Ajustes > Dispositivos y servicios
2. Haz clic en "+ Añadir integración"
3. Busca "SYR Connect"
4. Introduce las credenciales de la App SYR Connect:
   - Nombre de usuario
   - Contraseña

## Funcionalidades

La integración crea automáticamente entidades para todos tus dispositivos SYR Connect.

### Dispositivos soportados

Funciona con suavizadores de agua SYR que aparecen en el portal SYR Connect.

Probado y reportado funcionando:
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect

No probado, pero debería funcionar:
- NeoSoft 2500 Connect
- NeoSoft 5000 Connect
- SYR LEX Plus 10 Connect / SLIM
- SYR LEX Plus 10 IP (cuando esté vinculado mediante SYR Connect)
- SYR LEX 1500 Connect Einzel
- SYR LEX 1500 Connect Doppel
- SYR LEX 1500 Connect Pendel
- SYR LEX 1500 Connect Dreifach
- SYR IT 3000 Pendelanlage
- Otros modelos SYR con capacidad Connect o gateway retrofit

**Nota**: Si el dispositivo es visible en tu cuenta SYR Connect, la integración lo detectará automáticamente y creará las entidades. Para dispositivos no probados, compartir los datos de diagnóstico ayuda a ampliar la compatibilidad.

### Funcionalidad soportada

#### Sensores
- Monitorización de dureza de agua entrada/salida
- Capacidad restante
- Capacidad total
- Unidad de dureza
- Estado de regeneración (activo/inactivo)
- Número de regeneraciones
- Intervalo y horario de regeneración
- Gestión de sal (volumen, reserva)
- Monitorización de presión y caudal
- Estado operativo y alarmas

#### Sensores binarios
- Regeneración activa
- Estado operativo
- Alarmas

#### Botones (Acciones)
- Regenerar ahora (`setSIR`)
- Regeneración múltiple (`setSMR`)
- Reiniciar dispositivo (`setRST`)

### Limitaciones conocidas

- Dependencia de la nube: requiere conexión a Internet y servicio SYR Connect
- Intervalo mínimo recomendado: 60 segundos
- Mayormente lectura: sólo las acciones de regeneración están disponibles
- Una cuenta SYR Connect por instancia Home Assistant
- Sin API local: comunicación vía cloud

## Cómo se actualizan los datos

La integración consulta la API SYR Connect a intervalos regulares (por defecto 60s):

1. Inicio de sesión
2. Descubrimiento de dispositivos
3. Recuperación de estados
4. Actualización de las entidades en Home Assistant

Si un dispositivo está offline, las entidades estarán `unavailable` hasta la próxima actualización exitosa.

## Ejemplos de uso
- Automatizaciones: alerta de sal baja, informe diario de regeneración, notificación de alarmas, monitorización de caudal, regeneración programada (ver README original para ejemplos)

## Opciones de configuración

El intervalo de escaneo puede ajustarse en las opciones de la integración (por defecto 60s).

## Eliminación

1. Ajustes > Dispositivos y servicios
2. Selecciona SYR Connect
3. Menú (⋮) > Eliminar

## Solución de problemas

- Se pueden descargar datos de diagnóstico (los datos sensibles se enmascaran)
- Errores de conexión/autenticación: comprueba credenciales, prueba la app, revisa los logs

## Dependencias

- `pycryptodomex==3.19.0`

## Licencia

Licencia MIT - ver archivo LICENSE

## Agradecimientos

- Basado en el adaptador [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) de TA2k.
- Gracias al equipo SYR IoT por los logos.
