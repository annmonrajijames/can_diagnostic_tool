# can_decoder_gui.py  (Motorola fix)
# -----------------------------------------------------------
# • ONE central function: decode_signal()  ← fixed Motorola algo
# • Everything else unchanged
# -----------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv

try:
    import pandas as pd
except ImportError:
    pd = None

# ───────────────── helpers ─────────────────
def _to_int(val):
    s = str(val).strip().lower()
    try:
        return int(s, 10)
    except ValueError:
        return int(s, 16)

def _vbit(data: bytes, bit: int) -> int:
    return (data[bit // 8] >> (bit & 7)) & 1


# ─────── ONE decoding brain (Motorola fixed) ───────
def decode_signal(payload: bytes,
                  start: int,
                  length: int,
                  byte_order: str,
                  is_signed: bool,
                  scale: float,
                  offset: float):
    """
    Return the *physical* value using Vector numbering.

    • Intel  (little) → start bit is LSB, bits ascend
    • Motorola (big)  → start bit is MSB, bits descend **within each byte**
                         but jump +8 every full byte (Vector rule)
    """
    order_key = ''.join(byte_order.lower().split())
    motorola  = any(k in order_key for k in ("motorola", "big", "msb"))

    raw = 0
    if motorola:
        for i in range(length):
            # Vector Motorola rule: within a byte bits descend,
            # then jump +8 for each new byte chunk.
            bit = start + 8 * (i // 8) - (i % 8)
            raw = (raw << 1) | _vbit(payload, bit)
    else:  # Intel / little‑endian
        for i in range(length):
            raw |= _vbit(payload, start + i) << i

    if is_signed and raw & (1 << (length - 1)):
        raw -= 1 << length

    return raw * scale + offset


def decode_frame(msg_id, payload, sig_rows):
    if not sig_rows:
        raise ValueError(f"No signals defined for msg_id {msg_id}")

    out = []
    for r in sig_rows:
        phys = decode_signal(
            payload,
            r["start"], r["length"], r["byte_order"],
            bool(r.get("is_signed")),
            float(r.get("scale", 1)),
            float(r.get("offset", 0)),
        )
        out.append({
            "sig":    r["sig_name"],
            "start":  r["start"],
            "len":    r["length"],
            "order":  r["byte_order"],
            "scale":  r.get("scale", 1),
            "offset": r.get("offset", 0),
            "value":  phys,
        })
    return out


# ─────────── robust CSV loader (unchanged) ──────────
def load_signals(path: str):
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            if pd:
                df = pd.read_csv(path, encoding=enc)
                df.columns = df.columns.str.lower()
                df["msg_id"] = df["msg_id"].apply(_to_int)
                df["start"]  = df["start"].astype(int)
                df["length"] = df["length"].astype(int)
                return df.to_dict(orient="records")

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
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Unable to decode CSV with common encodings.")


# ───────────── Tkinter GUI (unchanged) ─────────────
class DecoderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CAN Frame Decoder")
        self.resizable(False, False)
        self.signals_db = None
        self._build_ui()

    def _build_ui(self):
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

        cols   = ("sig", "start", "len", "order", "scale", "offset", "value")
        widths = (140,   50,     45,    90,     60,      60,      90)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 10))

    # -------- callbacks --------
    def load_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.signals_db = load_signals(path)
            messagebox.showinfo("Loaded", f"Loaded {len(self.signals_db)} rows.")
        except Exception as e:
            messagebox.showerror("Error", f"CSV error:\n{e}")

    def decode(self):
        if not self.signals_db:
            messagebox.showwarning("No CSV", "Please load signals.csv first.")
            return
        try:
            txt = self.msg_entry.get().strip()
            try:
                msg_id = int(txt, 10)
            except ValueError:
                msg_id = int(txt, 16)

            parts = self.payload_entry.get().strip().split()
            if len(parts) != 8:
                raise ValueError("Need exactly 8 hex bytes.")
            payload = bytes(int(b, 16) for b in parts)

            rows = [r for r in self.signals_db if int(r["msg_id"]) == msg_id]
            table = decode_frame(msg_id, payload, rows)

            self.tree.delete(*self.tree.get_children())
            for row in table:
                self.tree.insert("", "end",
                    values=(row["sig"], row["start"], row["len"], row["order"],
                            row["scale"], row["offset"], f"{row['value']:.6g}"))
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ─────────────────────── run ──────────────────────────
if __name__ == "__main__":
    DecoderApp().mainloop()
