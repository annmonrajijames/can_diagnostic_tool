# CAN Diagnostic Tool

A powerful, vendor-independent **desktop-based GUI application** for working with CAN bus data. This software allows you to:

- Upload and parse **DBC files**
- View **live decoded CAN messages**
- Log and record selected signal data
- Detect errors and abnormal parameters
- Plot real-time data in a separate window
- Transmit custom CAN messages using decoded signal names
- Organize parameters by category and filter/search signals

---

## 🚀 Features

- ✅ Live reception of raw CAN frames
- ✅ DBC file upload and decoding to human-readable signals
- ✅ Real-time display of up to 200+ parameters
- ✅ Keyword-based parameter search
- ✅ Select/Deselect signals to monitor
- ✅ CSV logging with user-defined delay (e.g. 50ms, 100ms)
- ✅ Error and CAN loss detection
- ✅ Highlight abnormal values
- ✅ Live plotting in separate window
- ✅ System timestamp, GPS (latitude/longitude) fetch
- ✅ Modular and extensible architecture
- ✅ Clean PySide6 UI with navigation across pages
- ✅ Future-ready for any hardware vendor (supports plug-in drivers)

---

## 📦 Project Structure
```text
can_diagnostic_tool/
├── CAN_diagnostic_tool/                     # General CAN diagnostic GUI
│   ├── main.py                              # Entry point (general tool)
│   ├── PEAK_API.py                          # PEAK hardware API wrapper
│   ├── Sloki_API.py                         # Sloki hardware API wrapper
│   ├── dbc_page.py
│   ├── imp_params.py
│   ├── live_signal_viewer.py
│   └── Released_version/                    # Frozen release variant
│       ├── release_main.py                  # Entry for released build
│       ├── PEAK_API.py
│       ├── dbc_page.py
│       ├── imp_params.py
│       └── DBC_sample_cantools.dbc
│
├── CAN_tools/                               # Utilities and converters
│   ├── cantools_compatible.py
│   ├── Clean_dbcTOcsv.py
│   ├── csvTostandardizedDBC.py
│   ├── dbc_cantools_decoder.py
│   ├── decode_signal_fun_validater.py
│   └── PCAN_can_decoder.py
│
├── Only_Sloki_software/                     # Sloki‑only application
│   ├── only_Sloki_main.py                   # Entry point (Sloki only)
│   ├── config.json
│   ├── can_frame/
│   │   └── frame_page.py
│   ├── hardware/
│   │   ├── can_interface.py
│   │   └── driver_loader.py
│   ├── threads/
│   │   └── receiver_thread.py
│   └── ui/
│       ├── __init__.py
│       ├── hardware_page.py
│       └── main_window.py
│
├── BySlokiTeam_OriginalSampleCodes/         # Sloki team interface modules
│   ├── J2534_Driver.py
│   ├── sBus_J2534_Api.py
│   └── sloki_one_code.py
│
├── PEAK_VS_Sloki_benchmark/                 # Benchmark scripts
│   ├── PEAK_EachCANID.py
│   ├── PEAK_Stats.py
│   ├── Sloki_EachCANID.py
│   └── Sloki_Stats.py
│
├── CAN_tools/                               # DBC/data helpers
│   └── ...
│
├── data/                                    # Datasets, logs, DBCs (user)
│   ├── DBC_sample.dbc
│   ├── DBC_sample_cantools.dbc
│   └── signals.csv
└── README.md
```


---

## 🛠️ Requirements

- Python 3.11+
- PySide6
- cantools
- pyqtgraph (for plotting)
- pywin32 (for Windows GPS API)

---

## 🧩 Building the Windows .exe (PyInstaller)

### Prerequisites
- Install PEAK PCAN drivers for your device (Windows).
- Place `PCANBasic.dll` in `CAN_diagnostic_tool/Released_version/` (same folder as `release_main.py`).
- Ensure the release DBC file exists at `CAN_diagnostic_tool/Released_version/DBC_sample_cantools.dbc`.

### Code changes that enable frozen builds
- `CAN_diagnostic_tool/Released_version/PEAK_API.py`
  - Preloads `PCANBasic.dll` on startup using `os.add_dll_directory` + `ctypes.WinDLL` so python-can's PCAN backend can initialize in frozen builds.
  - Resolves the base directory correctly for PyInstaller (checks `sys._MEIPASS` and `sys.executable`).
  - Wraps CAN bus initialization with a safe fallback to `DummyBus` and prints a clear error if hardware init fails.
- `CAN_diagnostic_tool/Released_version/imp_params.py`
  - Shows a warning dialog if running on `DummyBus` (no live data) and a critical error dialog if backend init fails.
- `CAN_diagnostic_tool/Released_version/dbc_page.py`
  - Resolves DBC path for both normal and frozen runs (checks `sys._MEIPASS` / exe dir). The DBC must be bundled next to the exe.

### Build using the provided spec (recommended for this project)
If `CAN_diagnostic_tool/Released_version/CAN_Diagnostic_Tool.spec` is missing, create it with the following content, saved at that exact path:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['release_main.py'],
    pathex=[],
    binaries=[('PCANBasic.dll', '.')],
    datas=[('DBC_sample_cantools.dbc', '.')],
    hiddenimports=[
        'imp_params',
        'can',
        'can.interfaces',
        'can.interfaces.pcan',
        'can.interfaces.pcan.pcan',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CAN_Diagnostic_Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

Then build from the `CAN_diagnostic_tool/Released_version/` directory:

```powershell
python -m PyInstaller --noconfirm CAN_Diagnostic_Tool.spec
```

Result: `CAN_diagnostic_tool/Released_version/dist/CAN_Diagnostic_Tool.exe`.

### Verifying the build
- Double-click the generated exe. The GUI should open quickly and start showing decoded signals if CAN is present.
- If nothing appears and you want diagnostics, temporarily build with a console by adding `--console` (or setting `console=True` in the spec) and watch for:
  - “PCANBasic preloaded: …”
  - “Loaded DBC: … (messages: N)”
  - Any error indicating the PCAN bus failed to init (app will fall back to DummyBus and show a warning).

### Troubleshooting
- No data in exe but works in source run:
  - Ensure `PCANBasic.dll` is next to the exe (`dist` folder) and PEAK drivers are installed.
  - Check `PCAN_CHANNEL` and `BITRATE` in `PEAK_API.py` match your hardware; enable CAN FD options if applicable.
  - Confirm the DBC file name/path matches `dbc_page.py` config and is bundled.
- Need logs without a console window:
  - Add a file logger in `PEAK_API.py` or `imp_params.py` to capture initialization messages to a log file.