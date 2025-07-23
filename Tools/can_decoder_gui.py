# can_decoder_gui.py
# -----------------------------------------------------------
# Desktop CAN‑frame decoder – Vector DBC rules
# • ONE central function: decode_signal() RETURNS *physical* ONLY
# • Tkinter GUI (bundled with Python)
# • pandas optional (falls back to csv module)
# -----------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv

try:
    import pandas as pd        # optional speed‑up
except ImportError:
    pd = None


# ────────────────── helper utilities ─────────────────────
def _to_int(val):
    """decimal, 0x…, or bare hex → int."""
    s = str(val).strip().lower()
    try:
        return int(s, 10)
    except ValueError:
        return int(s, 16)


def _vbit(data: bytes, bit: int) -> int:
    """Vector bit numbering: bit‑0 = LSB of byte‑0."""
    return (data[bit // 8] >> (bit & 7)) & 1


# ───────────────── SINGLE decoding brain ─────────────────
def decode_signal(payload: bytes,
                  start: int,
                  length: int,
                  byte_order: str,
                  is_signed: bool,
                  scale: float,
                  offset: float):
    """
    Return the physical (human‑readable) value of ONE signal.

    Vector DBC rules:
      • Intel  (little) → start bit is LSB, bits ascend
      • Motorola (big)  → start bit is MSB, bits descend
    """
    order_key = ''.join(byte_order.lower().split())
    motorola  = any(k in order_key for k in ("motorola", "big", "msb"))

    raw = 0
    if motorola:
        for i in range(length):
            raw = (raw << 1) | _vbit(payload, start - i)
    else:  # Intel
        for i in range(length):
            raw |= _vbit(payload, start + i) << i

    if is_signed and raw & (1 << (length - 1)):
        raw -= 1 << length

    return raw * scale + offset


def decode_frame(msg_id: int, payload: bytes, sig_rows):
    """
    Return list‑of‑dicts (one per signal) with all arguments + physical value.
    """
    if not sig_rows:
        raise ValueError(f"No signals defined for msg_id {msg_id}")

    out = []
    for r in sig_rows:
        phys = decode_signal(
            payload,
            start      = r["start"],
            length     = r["length"],
            byte_order = r["byte_order"],
            is_signed  = bool(r.get("is_signed")),
            scale      = float(r.get("scale", 1)),
            offset     = float(r.get("offset", 0)),
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


# ───────────── robust CSV loader (hex‑aware) ─────────────
def load_signals(path: str):
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            if pd:                        # pandas path
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

        except UnicodeDecodeError as e:
            last_err = e
            continue

    raise UnicodeDecodeError(last_err.encoding, last_err.object,
                             last_err.start, last_err.end,
                             f"Could not decode CSV; tried {', '.join(encodings)}")


# ───────────────────── Tkinter GUI ───────────────────────
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

        cols   = ("sig", "start", "len", "order", "scale", "offset", "value")
        widths = (140,   50,     45,    90,     60,      60,      90)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.grid(row=4, column=0, columnspan=2,
                       padx=10, pady=(0, 10))

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
            # msg_id parse (decimal first, hex fallback)
            txt = self.msg_entry.get().strip()
            try:
                msg_id = int(txt, 10)
            except ValueError:
                msg_id = int(txt, 16)

            # payload parse
            parts = self.payload_entry.get().strip().split()
            if len(parts) != 8:
                raise ValueError("Enter exactly 8 hex bytes separated by spaces.")
            payload = bytes(int(b, 16) for b in parts)

            # subset & decode
            rows = [r for r in self.signals_db if int(r["msg_id"]) == msg_id]
            table = decode_frame(msg_id, payload, rows)

            self.tree.delete(*self.tree.get_children())
            for row in table:
                self.tree.insert(
                    "", "end",
                    values=(row["sig"], row["start"], row["len"], row["order"],
                            row["scale"], row["offset"],
                            f"{row['value']:.6g}")
                )

        except Exception as e:
            messagebox.showerror("Error", str(e))


# ───────────────────────── run app ───────────────────────
if __name__ == "__main__":
    DecoderApp().mainloop()
