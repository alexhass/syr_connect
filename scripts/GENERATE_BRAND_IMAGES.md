# Home Assistant Brand Images Generator

This script generates all required PNG logos and icons for the Home Assistant integration according to the [brands repository](https://github.com/home-assistant/brands) guidelines.

## Requirements

- Python 3.7 or newer
- Pillow library (for image processing)
- Source file: The logo must be a PNG file in the `scripts` folder, e.g. `syr_logo_cmyk.original.png`

## Installation

1. Install Pillow:

```bash
pip install Pillow
```

2. Copy your logo file to the `scripts` folder and adjust the filename in the script (`generate_brand_images.py`) if necessary.
   The default source path in the script is `syr_logo_cmyk.original.png`.

## Usage

Run the script from the `scripts` folder:

```bash
python generate_brand_images.py
```

The generated files will be placed in `custom_components/syr_connect`:
- `icon.png`
- `icon@2x.png`
- `logo.png`
- `logo@2x.png`

## Notes

- Image sizes and filenames follow Home Assistant requirements.
- The script can be customized for other filenames or sizes if needed.

## Troubleshooting

- If you get a `FileNotFoundError`, check that the filename in `SOURCE_PATH` is set to `syr_logo_cmyk.original.png` and the file exists in the `scripts` folder.
- If you get a Pillow import error, make sure Pillow is installed in your Python environment.

---

For questions or details, see the [brands repository](https://github.com/home-assistant/brands) for requirements.