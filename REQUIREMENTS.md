# System Requirements for SYR Connect Integration

## Home Assistant Requirements

- **Home Assistant Version**: 2023.1.0 or higher (recommended: latest stable)
- **Python Version**: 3.11 or higher (included in Home Assistant)

## Development Requirements

For running tests and development:

```bash
pip install pytest pytest-homeassistant-custom-component pytest-cov
```

Run tests with:

```bash
pytest tests/
```

Run tests with coverage:

```bash
pytest --cov=custom_components.syr_connect --cov-report=term-missing tests/
```

## Python Package Requirements

The following packages will be automatically installed by Home Assistant:

### Required Packages

1. **pycryptodomex** (==3.19.0)
   - Purpose: AES encryption/decryption for API communication
   - License: BSD, Public Domain
   - Note: Uses `pycryptodomex` (not `pycryptodome`) to avoid conflicts with Home Assistant's crypto libraries

2. **defusedxml** (==0.7.1)
   - Purpose: Secure XML parsing to prevent XXE (XML External Entity) attacks
   - License: Python Software Foundation License
   - Note: Replaces the built-in `xml.etree.ElementTree` with a hardened version

## Network Requirements

- **Internet Connection**: Required for cloud API access
- **API Endpoint**: <https://syrconnect.de/WebServices/>
- **Ports**: 443 (HTTPS)

## Installation Verification

After installing the integration in Home Assistant:

1. Check that requirements are installed:
   - Go to **Settings > System > Logs**
   - Look for any `ModuleNotFoundError` or `ImportError`
   - If requirements are missing, restart Home Assistant

2. Verify integration loads:
   - Go to **Settings > Devices & Services**
   - Check if "SYR Connect" appears in the list
   - If not visible, check logs for errors

3. Test connection:
   - Add the integration with your credentials
   - Check if devices are discovered
   - Verify sensors show data

## Common Issues

### Issue: `ModuleNotFoundError: No module named 'Cryptodome'` or `No module named 'defusedxml'`

**Solution**: Restart Home Assistant to trigger automatic installation of required packages (pycryptodomex and defusedxml)

### Issue: `ImportError: cannot import name 'AES' from 'Crypto.Cipher'`

**Solution**: This indicates a conflict with the old pycryptodome package. The integration now uses pycryptodomex which avoids this conflict.

### Issue: Integration not appearing in list

**Solution**:

1. Verify the folder structure is correct: `config/custom_components/syr_connect/`
2. Check that all required files are present
3. Restart Home Assistant
4. Check logs for any Python syntax errors

## Manual Dependency Installation (Advanced)

If automatic installation fails, you can manually install the dependencies:

```bash
# For Home Assistant Container/OS
docker exec -it homeassistant pip install pycryptodomex==3.19.0 defusedxml==0.7.1

# For Home Assistant Core
source /srv/homeassistant/bin/activate
pip install pycryptodomex==3.19.0 defusedxml==0.7.1
```

## File Structure Requirements

```
config/
└── custom_components/
   └── syr_connect/
      ├── __init__.py
      ├── manifest.json
      ├── config_flow.py
      ├── const.py
      ├── api.py
      ├── checksum.py
      ├── coordinator.py
      ├── sensor.py
      ├── button.py
      ├── binary_sensor.py
      ├── diagnostics.py
      ├── encryption.py
      ├── exceptions.py
      ├── helpers.py
      ├── http_client.py
      ├── payload_builder.py
      ├── repairs.py
      ├── response_parser.py
      ├── icon.png
      ├── icon@2x.png
      ├── logo.png
      ├── logo@2x.png
      └── translations/
         ├── de.json
         ├── en.json
         ├── es.json
         ├── fr.json
         ├── it.json
         └── pt.json
```

All files must be present for the integration to work correctly.
