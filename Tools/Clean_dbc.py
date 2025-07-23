#!/usr/bin/env python3
# Clean_dbc.py

import re
import csv

# Paths — adjust if needed
DBC_PATH   = r"C:\Users\annmo\Downloads\DBC_sample.dbc"
OUTPUT_CSV = r"C:\Users\annmo\Downloads\signals.csv"

# BO_  <id>  <name> : <dlc> <node>
_bo_re = re.compile(r'^BO_\s*(\d+)\s+(\S+)\s*:')
# SG_  <name> : <start_bit>|<length>@<endianness><sign> (<scale>,<offset>) [<min>|<max>] "<unit>"
_sg_re = re.compile(
    r'^\s+SG_\s+(\S+)\s*:\s*'
    r'(\d+)\|(\d+)@([01])([+-])\s*'
    r'\(\s*([0-9eE\.\-+]+)\s*,\s*([0-9eE\.\-+]+)\s*\)\s*'
    r'\[[^\]]*\]\s*'
    r'"([^"]*)"'
)

def sanitize(name: str) -> str:
    """Replace non-alphanumeric chars with underscores."""
    return re.sub(r'[^A-Za-z0-9_]', '_', name)

def format_pcan_id(can_id: int) -> str:
    """
    Format CAN ID like PCAN‑View:
    - Standard (0x000–0x7FF): 3 uppercase hex digits
    - Extended (>0x7FF): 8 uppercase hex digits
    """
    if can_id <= 0x7FF:
        return f"{can_id:03X}"
    else:
        return f"{can_id:08X}"

def parse_dbc(path):
    signals = []
    current_msg = None

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = _bo_re.match(line)
            if m:
                dbc_id    = int(m.group(1))
                # mask off the extended-frame flag (0x80000000)
                can_id    = dbc_id & 0x1FFFFFFF
                msg_name  = sanitize(m.group(2))
                current_msg = (format_pcan_id(can_id), msg_name)
                continue

            s = _sg_re.match(line)
            if s and current_msg:
                msg_id, msg_name = current_msg
                signals.append([
                    msg_id,
                    msg_name,
                    sanitize(s.group(1)),        # signal name
                    s.group(2),                  # start bit
                    s.group(3),                  # length
                    "little" if s.group(4) == "1" else "big",   # 1 = Intel (little‑endian), 0 = Motorola (big‑endian)
                    (s.group(5) == "-"),         # signed?
                    s.group(6),                  # scale
                    s.group(7),                  # offset
                    s.group(8)                   # unit
                ])

    return signals

def write_csv(signals, out_path):
    header = [
        'msg_id','msg_name','sig_name',
        'start','length','byte_order',
        'is_signed','scale','offset','unit'
    ]
    with open(out_path, 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(header)
        w.writerows(signals)
    print(f"✅ Wrote {len(signals)} signals to {out_path}")

if __name__ == "__main__":
    sigs = parse_dbc(DBC_PATH)
    write_csv(sigs, OUTPUT_CSV)
