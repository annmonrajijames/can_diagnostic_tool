#!/usr/bin/env python3
# parse_dbc.py

import re
import csv

# === adjust this if your DBC moves ===
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
    return re.sub(r'[^A-Za-z0-9_]', '_', name)

def parse_dbc(path):
    signals = []
    msg_id   = None
    msg_name = None

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = _bo_re.match(line)
            if m:
                msg_id   = m.group(1)
                msg_name = sanitize(m.group(2))
                continue

            s = _sg_re.match(line)
            if s and msg_id is not None:
                sig = [
                    msg_id,
                    msg_name,
                    sanitize(s.group(1)),
                    s.group(2),  # start
                    s.group(3),  # length
                    "big" if s.group(4) == "1" else "little",
                    (s.group(5) == "-"),
                    s.group(6),  # scale
                    s.group(7),  # offset
                    s.group(8),  # unit
                ]
                signals.append(sig)

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
