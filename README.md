# SYR Connect - Home Assistant Integration

This custom integration enables control of SYR Connect devices through Home Assistant.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add the repository URL
6. Select "Integration" as category
7. Click "Add"
8. Search for "SYR Connect" and install it
9. Restart Home Assistant

### Manual Installation

1. Copy the `syr_connect` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings > Devices & Services
2. Click "+ Add Integration"
3. Search for "SYR Connect"
4. Enter your SYR Connect App credentials:
   - Username
   - Password

## Features

The integration automatically creates entities for all your SYR Connect devices.

### Supported Devices

This integration supports the following SYR water softener models:
- SYR LEX Plus 10 Connect
- Other SYR Connect-enabled water softeners

**Note**: Devices must be connected to the SYR Connect cloud service via the SYR Connect App.

### Supported Functionality

#### Sensors
The integration provides comprehensive monitoring of your water softener:

**Water Quality & Capacity**
- Input/Output water hardness monitoring
- Remaining capacity tracking
- Total capacity information
- Water hardness unit display

**Regeneration Information**
- Regeneration status (active/inactive)
- Number of regenerations performed
- Regeneration interval settings
- Regeneration time schedule

**Salt Management**
- Salt volume in containers (1-3)
- Salt stock levels
- Estimated salt supply duration

**System Monitoring**
- Water pressure monitoring
- Flow rate (current)
- Flow counter (total consumption)
- Operating state
- Alarm status

**Device Information** (disabled by default, available in diagnostics category)
- Serial number
- Firmware version and model
- Device type and manufacturer
- Network information (IP, MAC, Gateway)

#### Binary Sensors
- Regeneration active status
- Operating state
- Screen lock status
- Alarm status

#### Buttons (Actions)
- **Regenerate Now (setSIR)**: Start immediate regeneration
- **Multi Regenerate (setSMR)**: Multiple regeneration cycle
- **Reset Device (setRST)**: Reset device settings

### Known Limitations

- **Cloud Dependency**: This integration requires an active internet connection and functioning SYR Connect cloud service
- **Update Interval**: Minimum recommended update interval is 60 seconds to avoid API rate limiting
- **Read-Only Data**: Most sensors are read-only; only regeneration actions can be triggered
- **Single Account**: Each Home Assistant instance can only connect to one SYR Connect account
- **No Local API**: The integration uses the cloud API; no local network communication is possible

## How Data is Updated

The integration polls the SYR Connect cloud API at regular intervals (default: 60 seconds):

1. **Login**: Authenticates with the SYR Connect API using your credentials
2. **Device Discovery**: Retrieves all projects and devices associated with your account
3. **Status Updates**: For each device, fetches current status including all sensor values
4. **Entity Updates**: Updates all Home Assistant entities with the latest values

If a device becomes unavailable (e.g., offline or communication error), its entities are marked as unavailable until the next successful update.

## Use Cases & Examples

### Automation Examples

#### Low Salt Alert
Get notified when salt supply is running low:

```yaml
automation:
  - alias: "SYR: Low Salt Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.SERIAL_NUMBER_getSS1
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
            Regenerations today: {{ states('sensor.SERIAL_NUMBER_getNOR') }}
            Remaining capacity: {{ states('sensor.SERIAL_NUMBER_getRES') }}L
            Salt supply: {{ states('sensor.SERIAL_NUMBER_getSS1') }} weeks
```

#### Alarm Notification
Immediate notification when an alarm is triggered:

```yaml
automation:
  - alias: "SYR: Alarm Notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.SERIAL_NUMBER_getALM
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Water Softener Alarm"
          message: "Check your SYR device - alarm detected!"
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
        entity_id: sensor.SERIAL_NUMBER_getFLO
        above: 20  # Flow rate above 20 L/min
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "High Water Flow Detected"
          message: "Unusual water flow - check for leaks!"
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
          entity_id: button.SERIAL_NUMBER_setSIR
```

**Note**: Replace `SERIAL_NUMBER` with your actual device serial number in all examples.

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
- `xmltodict==0.13.0`: For parsing XML responses
- `pycryptodomex==3.19.0`: For AES encryption/decryption

**Important**: The integration uses `pycryptodomex` (not `pycryptodome`) to avoid conflicts with Home Assistant's built-in crypto libraries.

These packages are **automatically installed** by Home Assistant when you:
1. Add the integration through the UI
2. Restart Home Assistant after installation

For detailed system requirements and troubleshooting, see [REQUIREMENTS.md](REQUIREMENTS.md).

## License

MIT License - see LICENSE file

## Credits

Based on the [ioBroker.syrconnectapp](https://github.com/TA2k/ioBroker.syrconnectapp) adapter by TA2k.
