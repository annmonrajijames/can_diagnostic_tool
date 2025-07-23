# can_decoder_gui.py
# -----------------------------------------------------------
# Desktop CAN‑frame decoder – Vector DBC bit rules
#   • Tkinter GUI (bundled with Python)
#   • pandas optional; falls back to csv.DictReader
#   • Diagnostic table: shows start, len, order, scale, offset, raw, value
# -----------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any
import csv

# ──────────────── optional pandas import ────────────────
try:
    import pandas as pd
except ImportError:
    pd = None

# ────────────────── bit‑level helpers ────────────────────
def _vbit(data: bytes, bit: int) -> int:
    """Vector bit numbering: bit‑0 = LSB of byte‑0."""
    return (data[bit // 8] >> (bit & 7)) & 1


def _raw_intel(data: bytes, start: int, length: int) -> int:
    """Intel/little‑endian: start is LSB, bits ascend ↑."""
    return sum(_vbit(data, start + i) << i for i in range(length))


def _raw_motorola(data: bytes, start: int, length: int) -> int:
    """Motorola/big‑endian: start is MSB, bits descend ↓."""
    val = 0
    for i in range(length):
        val = (val << 1) | _vbit(data, start - i)
    return val


def _raw_value(data: bytes, start: int, length: int, order: str) -> int:
    """
    Dispatch to Intel or Motorola extractor.

    Accepts variations like "Motorola MSB", "BIG_ENDIAN", "big", "msb", …
    """
    order_key = ''.join(order.lower().split())  # strip spaces, lower
    is_big = any(k in order_key for k in ("motorola", "big", "msb"))
    return (_raw_motorola if is_big else _raw_intel)(data, start, length)


# ─────────────── signal‑row → physical value ─────────────
def decode_frame(msg_id: int, payload: bytes, sig_rows):
    if not sig_rows:
        raise ValueError(f"No signals defined for msg_id {msg_id}")

    decoded_rows = []
    for r in sig_rows:
        raw = _raw_value(payload, r["start"], r["length"], r["byte_order"])

        if r.get("is_signed") and raw & (1 << (r["length"] - 1)):
            raw -= 1 << r["length"]

        scale  = float(r.get("scale", 1))
        offset = float(r.get("offset", 0))
        phys   = raw * scale + offset

        decoded_rows.append({
            "sig":    r["sig_name"],
            "start":  r["start"],
            "len":    r["length"],
            "order":  r["byte_order"],
            "scale":  scale,
            "offset": offset,
            "raw":    f"0x{raw:X}",
            "value":  phys,
        })
    return decoded_rows


# ─────────────────── CSV loading helpers ──────────────────
def _to_int(val):
    """Handle decimal, 0x…, or bare hex strings."""
    s = str(val).strip().lower()
    try:
        return int(s, 10)
    except ValueError:
        return int(s, 16)


def load_signals(path: str):
    """
    Read signals.csv with encoding fallback and hex‑aware msg_id parsing.
    Returns list‑of‑dict rows with lowercase keys.
    """
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_err = None

    for enc in encodings:
        try:
            # ---------- pandas branch ----------
            if pd:
                df = pd.read_csv(path, encoding=enc)
                df.columns = df.columns.str.lower()
                df["msg_id"] = df["msg_id"].apply(_to_int)
                df["start"]  = df["start"].astype(int)
                df["length"] = df["length"].astype(int)
                return df.to_dict(orient="records")

            # ---------- csv module branch ----------
            rows = []
            with open(path, newline='', encoding=enc) as f:
                rdr = csv.DictReader(f)
                for row in rdr:
                    row = {k.lower(): v for k, v in row.items()}
                    row["msg_id"] = _to_int(row["msg_id"])
                    row["start"]  = int(row["start"])
                    row["length"] = int(row["length"])
                    rows.append(row)
            return rows

        except UnicodeDecodeError as e:
            last_err = e
            continue

    raise UnicodeDecodeError(
        last_err.encoding, last_err.object,
        last_err.start, last_err.end,
        f"Could not decode CSV; tried {', '.join(encodings)}"
    )


# ───────────────────── Tkinter GUI ────────────────────────
class DecoderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAN Frame Decoder")
        self.resizable(False, False)
        self.signals_db = None
        self._build_widgets()

    def _build_widgets(self):
        ttk.Button(self, text="Load signals.csv", command=self.load_csv
                   ).grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        ttk.Label(self, text="msg_id").grid(row=1, column=0, sticky="e")
        self.msg_entry = ttk.Entry(self, width=28)
        self.msg_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(self, text="payload (8 hex bytes)").grid(row=2, column=0, sticky="e")
        self.payload_entry = ttk.Entry(self, width=28)
        self.payload_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(self, text="Decode", command=self.decode
                   ).grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")

        # Diagnostic table
        cols = ("sig", "start", "len", "order", "scale",
                "offset", "raw", "value")
        widths = (140, 50, 45, 90, 60, 60, 70, 90)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 10))

    # ---------- callbacks ----------
    def load_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.signals_db = load_signals(path)
            messagebox.showinfo("Loaded",
                                f"Loaded {len(self.signals_db)} signal rows.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{e}")

    def decode(self):
        if not self.signals_db:
            messagebox.showwarning("No CSV", "Please load signals.csv first.")
            return
        try:
            # msg_id parsing: decimal first, hex fallback
            txt = self.msg_entry.get().strip()
            try:
                msg_id = int(txt, 10)
            except ValueError:
                msg_id = int(txt, 16)

            # payload parsing
            parts = self.payload_entry.get().strip().split()
            if len(parts) != 8:
                raise ValueError("Enter exactly 8 hex bytes separated by spaces.")
            payload = bytes(int(b, 16) for b in parts)

            # subset & decode
            rows = [r for r in self.signals_db if int(r["msg_id"]) == msg_id]
            decoded_rows = decode_frame(msg_id, payload, rows)

            # display
            self.tree.delete(*self.tree.get_children())
            for row in decoded_rows:
                self.tree.insert("", "end", values=(
                    row["sig"], row["start"], row["len"], row["order"],
                    row["scale"], row["offset"], row["raw"],
                    f"{row['value']:.6g}"
                ))

        except Exception as e:
            messagebox.showerror("Error", str(e))


# ───────────────────────── run app ────────────────────────
if __name__ == "__main__":
    DecoderApp().mainloop()
