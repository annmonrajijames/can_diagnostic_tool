#!/usr/bin/env python3
"""
csv_to_dbc_full.py  –  Convert a Vector‑style signal table (signals.csv)
                        into a fully‑standard DBC that `cantools` can load.

* Preserves **all** rows (231 in your file).
* Detects genuine overlaps inside the same multiplex context.
* Auto‑corrects the frame type: IDs > 0x7FF are written as “extended”.
"""

from pathlib import Path
from collections import defaultdict
import pandas as pd
import re

# ── USER PATHS ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

CSV_IN  = BASE_DIR / "data" / "signals.csv"
DBC_DIR = BASE_DIR / "data"
DBC_OUT = DBC_DIR / "DBC_sample_cantools.dbc"
# ───────────────────────────────────────────────────────────────────────────

# ── HELPERS ────────────────────────────────────────────────────────────────
def sanitize(name: str) -> str:
    """Replace characters that Vector dislikes with '_'."""
    return re.sub(r'[^A-Za-z0-9_]', '_', str(name))

def vector_bits(start: int, length: int, byte_order: str):
    """
    Return the *exact* bit indices (0‑based) a signal occupies,
    following Vector’s numbering:
        • Intel  (little‑endian): ascending bits
        • Motorola (big‑endian): descending bits inside each byte,
          jump +8 at every byte boundary.
    """
    if byte_order.lower().startswith("l"):  # Intel / little‑endian
        return list(range(start, start + length))

    # Motorola / big‑endian (Vector rule)
    bits = []
    for i in range(length):
        byte_jump = i // 8
        bit = start + 8 * byte_jump - (i % 8)
        bits.append(bit)
    return bits

# ── LOAD CSV ───────────────────────────────────────────────────────────────
if not CSV_IN.exists():
    raise FileNotFoundError(CSV_IN)
df = pd.read_csv(CSV_IN)

# ── CONFLICT CHECK (optional but useful) ───────────────────────────────────
alloc = defaultdict(lambda: defaultdict(set))  # {msg_id: {mux_ctx: set(bits)}}
conflicts = []

for _, row in df.iterrows():
    msg_id = row["msg_id"]
    mux_ctx = row["mode"] if pd.notna(row["mode"]) and row["mode"] else "BASE"
    bits = vector_bits(int(row["start"]), int(row["length"]), row["byte_order"])

    # A multiplexor itself (usually mode == 'M') may share bits
    # with its children; we ignore collisions on the multiplexor row.
    is_mux_def = isinstance(row["mode"], str) and row["mode"].upper().startswith("M")

    if not is_mux_def:
        overlap = alloc[msg_id][mux_ctx].intersection(bits)
        if overlap:
            conflicts.append((msg_id, mux_ctx, row["sig_name"], sorted(overlap)))
        alloc[msg_id][mux_ctx].update(bits)
    else:
        alloc[msg_id][mux_ctx].update(bits)

if conflicts:
    print("⚠️  Genuine bit overlaps detected (same multiplex context):")
    for msg, mux, sig, overlap in conflicts:
        print(f"   – {sig} in message {msg} (ctx {mux}) overlaps bits {overlap}")
    print("   You *must* fix these rows in the CSV if cantools still rejects them.\n")

# ── BUILD DBC TEXT ─────────────────────────────────────────────────────────
lines = [
    'VERSION ""',
    "",
    "NS_ :",
    "    CM_",
    "BS_:",
    ""
]

for msg_hex, grp in df.groupby("msg_id"):
    first = grp.iloc[0]

    raw_id = int(msg_hex, 16)
    frame_type = first["frame_type"].strip().lower()
    if raw_id > 0x7FF:                     # auto‑correct mislabeled frames
        frame_type = "extended"
    dbc_id = raw_id | 0x80000000 if frame_type == "extended" else raw_id

    dlc = int(first["dlc"])
    msg_name = sanitize(first["msg_name"])
    msg_comment = "" if pd.isna(first["msg_comment"]) else str(first["msg_comment"])

    lines.append(f"BO_ {dbc_id} {msg_name}: {dlc} ECU")

    for _, row in grp.iterrows():
        sig_name = sanitize(row["sig_name"])
        mode = row["mode"] if pd.notna(row["mode"]) else ""
        start = int(row["start"]); length = int(row["length"])
        endian = "1" if row["byte_order"].lower().startswith("l") else "0"
        sign_char = "-" if int(row["is_signed"]) else "+"
        scale = float(row["scale"]); offset = float(row["offset"])
        lo = "" if pd.isna(row["min"]) else row["min"]
        hi = "" if pd.isna(row["max"]) else row["max"]
        unit = "" if pd.isna(row["unit"]) else row["unit"]

        sg = f"    SG_ {sig_name}"
        if mode:
            sg += f" {mode}"
        sg += f" : {start}|{length}@{endian}{sign_char} ({scale},{offset}) [{lo}|{hi}] \"{unit}\" ECU"
        lines.append(sg)

    lines.append("")
    if msg_comment:
        lines.append(f'CM_ BO_ {dbc_id} "{msg_comment}";')
    for _, row in grp.iterrows():
        if pd.notna(row["sig_comment"]) and row["sig_comment"] != "":
            lines.append(f'CM_ SG_ {dbc_id} {sanitize(row["sig_name"])} "{row["sig_comment"]}";')
    lines.append("")

# ── WRITE FILE ─────────────────────────────────────────────────────────────
DBC_DIR.mkdir(parents=True, exist_ok=True)
DBC_OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"✅  Wrote complete DBC with {len(df)} signals → {DBC_OUT}")
