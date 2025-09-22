# Build the Engineers .exe (PyInstaller)

This packages `main.py` into a Windows executable without bundling any `.dbc` files.

## Prerequisites
- Windows with Python 3.11+
- PyInstaller installed in your environment
- PEAK PCAN drivers installed
- `PCANBasic.dll` available (copied next to the exe by the spec)

## Build
From this folder:

```powershell
# Optional: create venv and install deps
# py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r ..\..\requirements.txt

python -m PyInstaller --noconfirm PEAK_Engineers_Tool.spec
```

Resulting exe:
`dist/CAN_Diagnostic_Tool_Engineers.exe`

## DBC handling (not bundled)
- No `.dbc` files are packaged. On first run, open Settings and select your `.dbc` file from disk. The path is stored in `settings.json` next to the exe.

## Troubleshooting
- If the app opens but no CAN frames appear, confirm:
  - `PCANBasic.dll` is next to the exe in `dist`.
  - PEAK drivers are installed.
  - Your bitrate/channel in `PEAK_API.py` match your hardware.
- For console logs, rebuild with console enabled:
  - Edit the spec and set `console=True`.
