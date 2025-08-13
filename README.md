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
├── BySlokiTeam_OriginalSampleCodes/            # Sloki team interface modules
│   ├── sloki_one_code.py
│   ├── sBus_J2534_Api.py
│   └── J2534_Driver.py
│
├── PEAK_VS_Sloki_benchmark/                 # Benchmark scripts
│   ├── PEAK_EachCANID.py
│   ├── PEAK_Stats.py
│   ├── Sloki_EachCANID.py
│   └── Sloki_Stats.py
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
