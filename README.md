# SYR Connect - Home Assistant Integration

[![GitHub Release](https://img.shields.io/github/release/alexhass/syr_connect.svg?style=flat)](https://github.com/alexhass/syr_connect/releases)
[![syr_connect installs](https://img.shields.io/badge/dynamic/json?logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.syr_connect.total)](https://my.home-assistant.io/redirect/config_flow_start/?domain=syr_connect)
[![hassfest](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hassfest.yaml)
[![HACS](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/hacs.yaml)
[![ci](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml/badge.svg)](https://github.com/alexhass/syr_connect/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexhass/syr_connect/graph/badge.svg?token=8P822HPPF3)](https://codecov.io/gh/alexhass/syr_connect)

This custom integration enables control of SYR Connect devices through Home Assistant.

![Syr](custom_components/syr_connect/logo.png)

## Screenshots

Examples of device interfaces:

![LEXplus10S screenshot](docs/assets/screenshots/en/lexplus10s.png)

![Safe-T+ screenshot](docs/assets/screenshots/en/safetplus.png)

## Disclaimer

### IMPORTANT: Read this before using the integration

This integration controls water treatment and water shut-off systems. Improper configuration or malfunctioning automations could result in water damage, system failures, or property damage.

- **Use at Your Own Risk**: This software is provided "as is" without warranty of any kind
- **Test Thoroughly**: Always test automations in safe conditions before deploying them
- **Critical Systems**: Valve control automations can shut off your entire water supply - test carefully
- **No Liability**: The authors and contributors are not responsible for any damages, water damage, property damage, or other issues resulting from the use of this integration
- **Cloud Dependency**: This integration relies on the SYR Connect cloud service - availability is not guaranteed
- **Backup Plan**: Ensure you have alternative access to your water shut-off valve in case of system failure

By installing and using this integration, you acknowledge these risks and agree to use it responsibly.

## Installation

### Home Assistant Community Store - [HACS](https://hacs.xyz/) (recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Search for "SYR Connect"
4. Click "Install"
5. Restart Home Assistant

### Manual Installation

1. Copy the `syr_connect` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

The integration supports two configuration modes:

### Cloud API Setup (All Devices)

1. Go to Settings > Devices & Services
2. Click "+ Add Integration"
3. Search for "SYR Connect"
4. Choose "Cloud Access"
5. Enter your SYR Connect App credentials:
   - **Username**: Your SYR Connect account email
   - **Password**: Your SYR Connect account password

### Local API Setup (Newer Devices Only)

For devices with local JSON API support (NeoSoft 2500/5000 Connect, SafeTech Connect, TRIO DFR/LS Connect):

1. Go to Settings > Devices & Services
2. Click "+ Add Integration"
3. Search for "SYR Connect"
4. Choose "Local Access"
5. Enter the device information:
   - **Device Model**: Select your device model (e.g. NeoSoft 2500 Connect)
   - **Host**: IP address of your device (e.g., `192.168.178.199`)

**Note**: To find your device's IP address, check your router's DHCP client list or the device's display menu.

**Important**: For stable operation, the device must have a **static IP address** or a **reserved DHCP lease** (DHCP reservation). If the device's IP address changes, the integration will lose connection and needs to be reconfigured. Alternatively, you can use a hostname if your network supports local DNS resolution.

## Features

The integration automatically creates entities for all your SYR Connect devices.

### Supported Devices

This integration works with SYR water softeners and leakage detection devices and other that appear in the SYR Connect cloud (via the SYR Connect app).

Tested and reported as working:

- Sanibel Leak Protection Module A25
- Sanibel Softwater UNO A25
- SYR LEX 1500 Connect Single (LEX10/LEX20/LEX30/LEX40/LEX60/LEX80/LEX100)
- SYR LEX Plus 10 Connect
- SYR LEX Plus 10 S Connect
- SYR LEX Plus 10 SL Connect
- SYR NeoSoft 2500 Connect
- SYR SafeFloor Connect
- SYR Safe-T+ Connect
- SYR SafeTech Connect
- SYR SafeTech plus Connect
- SYR TRIO DFR/LS Connect 2425

Other devices are also of interest, but still need to be integrated (please report):

- Hansgrohe PontosBase
- Sanibel Softwater DUO A25
- SYR HygBox Connect
- SYR IT 3000 Pendulum system
- SYR LEX 1500 Connect Duplex
- SYR LEX 1500 Connect Alternating
- SYR LEX 1500 Connect Triple
- SYR NeoDos Connect
- SYR NeoSoft 5000 Connect
- Other SYR models with Connect capability or a retrofitted gateway that show up in the SYR Connect portal

**Note**: If the device is visible in your SYR Connect account, the integration will discover it and create the entities automatically. If you own an "untested device", it is helpful to share the diagnostic data to find out whether there are any unknown values or whether everything is working as desired. This also allows the list of tested devices to be continuously expanded.

### Supported Functionality

#### Sensors

The integration provides comprehensive monitoring of your devices:

#### Water Quality & Capacity

- Input/Output water hardness monitoring
- Water conductivity (µS/cm)
- Water temperature (°C)
- Remaining softening capacity tracking
- Resin capacity per tank (up to 3 tanks, %)
- Total volume monitoring
- Water hardness unit display

#### Regeneration Information

- Regeneration status and active-tank indicator (up to 3 tanks)
- Regeneration mode (Standard / ECO / Power / Automatic)
- Number of regenerations performed
- Last regeneration timestamp
- Regeneration interval settings
- Regeneration time schedule
- Cycle counters and timing

#### Salt Management

- Salt volume in containers (1-3)
- Salt stock levels (weeks remaining)
- Resin reserve capacity per bottle

#### System Monitoring

- Water pressure monitoring
- Flow rate (current and instantaneous)
- Flow counter (total consumption)
- Battery and mains voltage
- Alarm, notification, and warning status (current code and last 8 history entries)

#### Leak Protection (LEXplus10SL / Trio DFR/LS)

- Leak protection volume and duration limits (present and absent profiles)
- Active leak protection profile index
- Leak protection profiles 1–8 (volume limit, max duration, flow threshold, warning and buzzer flags)
- Temporary deactivation timer

#### Microleakage Testing (Trio DFR/LS)

- Microleakage test interval and status
- Test duration and event count

#### Self-Learning Phase (Trio DFR/LS)

- Remaining and elapsed self-learning time
- Flow rate and accumulated volume during self-learning

#### Filter (NeoSoft)

- Filter backwash countdown
- Iron content measurement

#### Maintenance

- Next scheduled maintenance dates (semi-annual and annual)
- Expected daily water consumption

#### Device Information

- Serial number
- Firmware version and model
- Device type and manufacturer
- Network information (IP, MAC, Gateway)
- Wi-Fi connectivity status and signal strength

#### Binary Sensors

- **Regeneration Active**: Indicates whether a regeneration cycle is currently running
- **Buzzer State**: Indicates whether the device buzzer is currently enabled

#### Buttons (Actions)

- **Regenerate Now**: Start immediate regeneration cycle
- **Reset Alarm**: Clear active alarm messages
- **Reset Notification**: Clear notification messages
- **Reset Warning**: Clear warning messages

#### Switch Controls

- **Buzzer**: Enable or disable the device buzzer

#### Select Controls (Configuration)

- **Regeneration Time**: Set the daily regeneration time (15-minute intervals)
- **Leak Protection Profile**: Select active leak protection profile (for devices with multiple profiles)
- **Salt Amount**: Configure salt quantity in containers (varies by model, up to 3 containers)
- **Regeneration Interval**: Set how often regeneration occurs (model dependent: 1–4 days)
- **Display Rotation**: Set the display orientation (0 / 90 / 180 / 270 degrees, for devices with a display)
- **Filter Backwash Interval**: Configure filter backwash frequency (for NeoSoft devices with filter)
- **Filter Type**: Select the installed filter type (for NeoSoft devices)

#### Valve Control

- **Water Shut-off Valve**: Control the main water shut-off valve
  - Open and close valve operations
  - Monitor current valve position and status
  - Integrate with leak detection automations for automatic shutoff

### API Modes

The integration supports two API modes:

#### Cloud API (XML-based)

- **Supported by**: All SYR Connect devices
- **Connection**: Via SYR Connect cloud service (syrconnect.de)
- **Authentication**: Username and password from SYR Connect account
- **Advantages**: Works with all device models, remote access from anywhere
- **Requirements**: Internet connection, SYR Connect account

#### Local API (JSON-based)

- **Supported by**: Select newer models with built-in local API (NeoSoft 2500/5000 Connect, SafeTech Connect, TRIO DFR/LS Connect)
- **Connection**: Direct to device via local network (port 5333)
- **Authentication**: No credentials required
- **Advantages**: No internet dependency, faster response times, no cloud rate limits
- **Requirements**: Device must be on same network as Home Assistant, device needs static IP address or hostname

The integration automatically detects which API mode to use based on the configuration provided during setup.

## How Data is Updated

The integration polls the device API at regular intervals (default: 60 seconds). The update process depends on the API mode:

### Cloud API Update Process

1. **Login**: Authenticates with the SYR Connect cloud API using your credentials
2. **Device Discovery**: Retrieves all projects and devices associated with your account
3. **Status Updates**: For each device, fetches current status including all sensor values
4. **Entity Updates**: Updates all Home Assistant entities with the latest values

### Local API Update Process

1. **Status Updates**: Directly fetches device status from the local endpoint
2. **Entity Updates**: Updates all Home Assistant entities with the latest values

The local API is faster and doesn't depend on internet connectivity, making it more reliable for real-time monitoring and automations.

If a device becomes unavailable (e.g., offline or communication error), its entities are marked as unavailable until the next successful update.

### Known Limitations

- **Cloud Dependency**: The cloud API requires an active internet connection and functioning SYR Connect cloud service
- **Update Interval**: Minimum recommended update interval is 60 seconds to avoid API rate limiting when using cloud API
- **Limited Write Access**: Configuration changes (regeneration time, salt amounts, intervals) and control actions (regeneration, valve control) are supported, but some advanced settings may only be available through the SYR Connect App
- **Local API Support**: Only some newer device models (NeoSoft 2500/5000 Connect, SafeTech Connect, TRIO DFR/LS Connect) provide a local JSON API. Most other models, including all LEXplus variants, require cloud API access

## Use Cases & Examples

### Automation Examples

#### Low Salt Alert

Get notified when salt supply is running low:

```yaml
automation:
  - alias: "SYR: Low Salt Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getss1
        below: 2  # Less than 2 weeks of salt remaining
    action:
      - service: notify.mobile_app
        data:
          title: "Water Softener Alert"
          message: "Salt supply low - less than 2 weeks remaining"
```

#### Daily Regeneration Report

Get a daily summary of regeneration activity:

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

#### Alarm Notification

Immediate notification when an alarm is triggered:

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

#### Water Flow Monitoring

Alert on unusually high water flow (possible leak):

```yaml
automation:
  - alias: "SYR: High Flow Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.syr_connect_<serial_number>_getflo
        above: 20  # Flow rate above 20 L/min
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "High Water Flow Detected"
          message: "Unusual water flow - check for leaks!"
```

#### Leak Sensor — Close Water Valve

Automatically close the water valve when a leak sensor detects water. This example uses the standard `valve.close` service to close the SYR water shut-off valve. Replace the entity IDs with the correct IDs from your system. Test very carefully that this automation works correctly, as it can become a critical safety action.

```yaml
automation:
  - alias: "SYR: Close Valve On Leak"
    description: "Set SYR valve to closed (setAB = true) when a leak sensor detects water."
    trigger:
      - platform: state
        entity_id: binary_sensor.house_leak_sensor
        to: 'on'
    action:
      - service: valve.close
        target:
          entity_id: valve.syr_connect_<serial_number>_getab
      - service: notify.mobile_app
        data:
          title: "SYR: Leak detected — valve closed"
          message: "Water leak detected — SYR water shut-off valve has been closed automatically."
```

#### Scheduled Regeneration Override

Trigger regeneration at a specific time:

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

**Note**: Replace `<serial_number>` with your actual device serial number in all examples.

## Configuration Options

### Scan Interval

Data is updated every 60 seconds by default. You can configure this in the integration options:

1. Go to Settings > Devices & Services
2. Find the SYR Connect integration
3. Click "Configure"
4. Adjust the scan interval (in seconds)

## Removal

To remove the integration from Home Assistant:

1. Go to Settings > Devices & Services
2. Find the SYR Connect integration
3. Click the three dots (⋮) menu
4. Select "Delete"
5. Confirm the deletion

All associated devices and entities will be automatically removed.

## Troubleshooting

### Download Diagnostics

If you encounter issues, you can download diagnostic information:

1. Go to Settings > Devices & Services
2. Find the SYR Connect integration
3. Click on the device
4. Click the three dots (⋮) menu
5. Select "Download diagnostics"

This file contains helpful information for troubleshooting (sensitive data like passwords are automatically redacted).

### Connection fails

- **Check credentials**: Verify your SYR Connect App username and password
- **Test the app**: Make sure you can log in to the SYR Connect mobile app
- **Check logs**: Go to Settings > System > Logs and search for "syr_connect" errors
- **Network issues**: Ensure your Home Assistant instance has internet access

### Authentication errors

If you see "Authentication failed" errors:

1. Verify your credentials are correct
2. The integration will prompt for reauthentication
3. Go to Settings > Devices & Services
4. Click "Authenticate" on the SYR Connect integration
5. Enter your credentials again

### No devices found

- **App setup**: Ensure devices are properly configured in the SYR Connect App
- **Account access**: Verify you're using the same account that has the devices
- **Device status**: Check if devices are online in the SYR Connect App
- **Logs**: Check Home Assistant logs for specific error messages

### Entities show as unavailable

- **Device offline**: Check if the device is online in the SYR Connect App
- **Network issues**: Verify internet connectivity
- **Cloud service**: The SYR Connect cloud service might be temporarily unavailable
- **Wait for update**: Entities will become available again on the next successful update

### High CPU/Memory usage

- **Increase scan interval**: Set a higher value (e.g., 120-300 seconds) in integration options
- This reduces API calls and system load

## Dependencies

The integration requires the following Python packages:

- `pycryptodomex>=3.19.0,<4.0`: For AES encryption/decryption
- `defusedxml>=0.7.1,<1.0`: For secure XML parsing (prevents XXE attacks)

**Note**: The integration uses `defusedxml` for secure XML parsing and `pycryptodomex` (not `pycryptodome`) to avoid conflicts with Home Assistant's built-in crypto libraries.

This package is **automatically installed** by Home Assistant when you:

1. Add the integration through the UI
2. Restart Home Assistant after installation

For detailed system requirements and troubleshooting, see [REQUIREMENTS.md](REQUIREMENTS.md).

## License

MIT License - see LICENSE file

## Credits

- Inspired by [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) adapter from TA2k.
- Many thanks to SYR IoT-Development-Team for sharing the logos.
