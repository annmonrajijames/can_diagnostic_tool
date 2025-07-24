#!/usr/bin/env python3
# clean_dbc.py  –  parse a DBC and dump an enriched signal table to CSV‑UTF8
#
# Columns captured
# ────────────────
# msg_id, msg_name, frame_type, dlc, msg_comment,
# sig_name, mode, start, length, byte_order, is_signed,
# scale, offset, min, max, unit, sig_comment
#
# ‼️  No external libraries are required.

import re
import csv
from pathlib import Path

# ── USER PATHS ──────────────────────────────────────────────────────────────
DBC_PATH   = Path(r"C:\Users\annmo\Downloads\DBC_sample.dbc")
OUTPUT_CSV = Path(r"C:\Users\annmo\Downloads\signals.csv")
# ────────────────────────────────────────────────────────────────────────────

# ── REGEXES ─────────────────────────────────────────────────────────────────
_bo_re = re.compile(r'^BO_\s*(\d+)\s+(\S+)\s*:\s*(\d+)\s+(.+)$')
_sg_re = re.compile(
    r'^\s+SG_\s+(\S+)'                # 1  signal name
    r'(?:\s+([Mm]\d*))?\s*'           # 2  multiplex info (optional)
    r':\s*(\d+)\|(\d+)@([01])([+-])'  # 3‑6 start, length, endian, sign
    r'\s*\(\s*([0-9eE.+-]+)\s*,\s*([0-9eE.+-]+)\s*\)'       # 7‑8 scale, offset
    r'\s*\[\s*([0-9eE.+-]*)\s*\|\s*([0-9eE.+-]*)\s*\]'      # 9‑10 min, max
    r'\s*"([^"]*)"'                   # 11 unit
)
_cm_msg = re.compile(r'^CM_\s+BO_\s+(\d+)\s+"([^"]+)"')
_cm_sig = re.compile(r'^CM_\s+SG_\s+(\d+)\s+(\S+)\s+"([^"]+)"')

# ── HELPERS ────────────────────────────────────────────────────────────────
def sanitize(name: str) -> str:
    """Replace non‑alphanumerics with underscores for safe CSV / filenames."""
    return re.sub(r'[^A-Za-z0-9_]', '_', name)

def format_pcan_id(can_id: int) -> str:
    """
    Return PCAN‑View style CAN ID **with `0x` prefix**:
      • standard frame  → 0x123
      • extended frame  → 0x18F20309
    """
    return f"0x{can_id:03X}" if can_id <= 0x7FF else f"0x{can_id:08X}"

# ── STEP 1: COLLECT COMMENTS (1st pass) ────────────────────────────────────
def collect_comments(path: Path):
    msg_comments = {}
    sig_comments = {}
    with path.open(encoding='utf-8', errors='ignore') as f:
        for line in f:
            if m := _cm_msg.match(line):
                msg_comments[int(m.group(1))] = m.group(2)
            elif s := _cm_sig.match(line):
                sig_comments[(int(s.group(1)), s.group(2))] = s.group(3)
    return msg_comments, sig_comments

# ── STEP 2: PARSE MAIN STRUCTURE (2nd pass) ────────────────────────────────
def parse_dbc(path: Path, msg_comments, sig_comments):
    """Return list[list[str]] – one row per signal with all required columns."""
    rows = []
    current_msg = None

    with path.open(encoding='utf-8', errors='ignore') as f:
        for line in f:
            if m := _bo_re.match(line):
                dbc_id  = int(m.group(1))
                can_id  = dbc_id & 0x1FFFFFFF
                frame_t = "extended" if dbc_id & 0x80000000 else "standard"
                current_msg = {
                    "dbc_id"    : dbc_id,
                    "id"        : format_pcan_id(can_id),        # 👈 0x‑prefixed
                    "name"      : sanitize(m.group(2)),
                    "dlc"       : int(m.group(3)),
                    "frame_type": frame_t,
                    "comment"   : msg_comments.get(dbc_id, "")
                }
                continue

            if s := _sg_re.match(line):
                if current_msg is None:
                    continue  # malformed DBC
                sig_name = s.group(1)
                rows.append([
                    current_msg["id"],                       # msg_id  (now 0x…)
                    current_msg["name"],                     # msg_name
                    current_msg["frame_type"],               # frame_type
                    current_msg["dlc"],                      # dlc
                    current_msg["comment"],                  # msg_comment
                    sanitize(sig_name),                      # sig_name
                    s.group(2) or "",                        # mode
                    s.group(3),                              # start
                    s.group(4),                              # length
                    "little" if s.group(5) == "1" else "big",# byte_order
                    (s.group(6) == "-"),                     # is_signed
                    s.group(7),                              # scale
                    s.group(8),                              # offset
                    s.group(9),                              # min
                    s.group(10),                             # max
                    s.group(11),                             # unit
                    sig_comments.get((current_msg["dbc_id"], sig_name), "")
                ])
    return rows

# ── STEP 3: WRITE CSV (UTF‑8 with BOM) ─────────────────────────────────────
def write_csv(rows, out_path: Path):
    header = [
        'msg_id','msg_name','frame_type','dlc','msg_comment',
        'sig_name','mode','start','length','byte_order','is_signed',
        'scale','offset','min','max','unit','sig_comment'
    ]
    with out_path.open('w', newline='', encoding='utf-8-sig') as fo:
        csv.writer(fo).writerows([header] + rows)
    print(f"✅ Wrote {len(rows)} signals → {out_path}")

# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not DBC_PATH.exists():
        raise FileNotFoundError(DBC_PATH)
    msg_cmt, sig_cmt = collect_comments(DBC_PATH)
    sig_rows = parse_dbc(DBC_PATH, msg_cmt, sig_cmt)
    write_csv(sig_rows, OUTPUT_CSV)
