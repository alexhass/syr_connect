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

### Sensors
- All device status values are created as sensors
- Automatic detection of values like water flow, salt level, etc.

### Buttons (Actions)
- **Regenerate Now (setSIR)**: Start immediate regeneration
- **Multi Regenerate (setSMR)**: Multiple regeneration
- **Reset Device (setRST)**: Reset device

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

### Connection fails
- Check your credentials
- Make sure you can access your account with the SYR Connect App
- Check the Home Assistant logs for detailed error messages

### No devices found
- Make sure your SYR Connect devices are set up in the app
- Check the logs for connection issues

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
