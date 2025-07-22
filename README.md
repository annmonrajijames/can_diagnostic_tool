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
- ✅ Dedicated page for real-time decoded parameters
- ✅ Future-ready for any hardware vendor (supports plug-in drivers)

---

## 📦 Project Structure
```text
can_diagnostic_tool/
├── main.py                       # Entry point
│
├── ui/                           # GUI layout & navigation
│   ├── __init__.py
│   ├── main_window.py            # Home page + stacked pages
│   └── dbc_page.py              # Real-time decoded parameters
│
├── can_frame/                    # “CAN Frame” feature module
│   ├── __init__.py
│   ├── frame_page.py             # Live frame table & delay stats
│   └── frame_controller.py       # (road‑map) decode / filter logic
│
├── threads/                      # Background workers
│   ├── receiver_thread.py        # Continuous CAN RX
│   └── logger_thread.py          # (road‑map) CSV/Parquet logger
│
├── hardware/                     # Interface abstraction
│   ├── can_interface.py          # High‑level wrapper
│   └── drivers/
│       └── j2534_sloki_driver.py # Sloki J2534 DLL binding
│
├── core/                         # Backend utilities
│   ├── dbc_decoder.py            # DBC parsing/decoding
│   ├── logger.py                 # Re‑usable logging helpers
│   ├── gps_location.py           # System‑time & optional GPS
│   └── config.py                 # Centralised settings
│
├── data/
│   ├── logs/                     # Recorded sessions
│   └── sample.dbc                # Example database
│
├── assets/
│   └── icons/                    # App icons / images
│
├── requirements.txt              # All Python dependencies
├── .gitignore                    # Git hygiene rules
└── README.md                     # ← **this file**

```                 


---

## 🛠️ Requirements

- Python 3.11+
- PySide6
- cantools
- pyqtgraph (for plotting)
- pywin32 (for Windows GPS API)
