#!/usr/bin/env python3
"""
csselectronicsDBC_to_cantoolsDBC.py – Clean a CSS Electronics/Vector-style DBC
and produce a cantools-compatible DBC in one pass.

Pipeline:
  1) Parse input .dbc into a normalized CSV (UTF-8 with BOM) with columns:
     msg_id,msg_name,frame_type,dlc,msg_comment,
     sig_name,mode,start,length,byte_order,is_signed,
     scale,offset,min,max,unit,sig_comment
  2) Read that CSV and generate a standard-compliant DBC that cantools can load.

Notes:
  • Message IDs in the CSV are PCAN-style hex strings with 0x prefix (e.g. 0x123, 0x18F20309).
  • Extended/standard frame type is auto-corrected: if id > 0x7FF → extended.
  • No external libraries required.

Usage:
  python csselectronicsDBC_to_cantoolsDBC.py -i data/DBC_sample.dbc -o data/DBC_sample_cantools.dbc \
      --csv data/signals.csv

If arguments are omitted, defaults under the repository's data/ folder are used.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# ── DEFAULT PATHS (relative to repo root) ───────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_IN_DBC = BASE_DIR / "data" / "DBC_sample.dbc"
DEFAULT_OUT_DBC = BASE_DIR / "data" / "DBC_sample_cantools.dbc"
DEFAULT_OUT_CSV = BASE_DIR / "data" / "signals.csv"

# ── REGEXES re-used from the cleaning step ─────────────────────────────────
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

# ── COMMON HELPERS ─────────────────────────────────────────────────────────
def sanitize(name: str) -> str:
    """Replace non‑alphanumerics with underscores for safe CSV / DBC names."""
    return re.sub(r'[^A-Za-z0-9_]', '_', str(name))

def format_pcan_id(can_id: int) -> str:
    """Return PCAN‑View style CAN ID with 0x prefix (standard/extended)."""
    return f"0x{can_id:03X}" if can_id <= 0x7FF else f"0x{can_id:08X}"

# ── STEP 1: COLLECT COMMENTS (1st pass on DBC) ─────────────────────────────
def collect_comments(path: Path) -> Tuple[Dict[int, str], Dict[Tuple[int, str], str]]:
    msg_comments: Dict[int, str] = {}
    sig_comments: Dict[Tuple[int, str], str] = {}
    with path.open(encoding='utf-8', errors='ignore') as f:
        for line in f:
            if m := _cm_msg.match(line):
                msg_comments[int(m.group(1))] = m.group(2)
            elif s := _cm_sig.match(line):
                sig_comments[(int(s.group(1)), s.group(2))] = s.group(3)
    return msg_comments, sig_comments

# ── STEP 2: PARSE DBC STRUCTURE (2nd pass) → rows for CSV ──────────────────
def parse_dbc_to_rows(path: Path, msg_comments: Dict[int, str], sig_comments: Dict[Tuple[int, str], str]) -> List[List[str]]:
    rows: List[List[str]] = []
    current_msg = None

    with path.open(encoding='utf-8', errors='ignore') as f:
        for line in f:
            if m := _bo_re.match(line):
                dbc_id  = int(m.group(1))
                can_id  = dbc_id & 0x1FFFFFFF
                frame_t = "extended" if dbc_id & 0x80000000 else "standard"
                current_msg = {
                    "dbc_id"    : dbc_id,
                    "id"        : format_pcan_id(can_id),
                    "name"      : sanitize(m.group(2)),
                    "dlc"       : int(m.group(3)),
                    "frame_type": frame_t,
                    "comment"   : msg_comments.get(dbc_id, ""),
                }
                continue

            if s := _sg_re.match(line):
                if current_msg is None:
                    continue  # malformed DBC line without BO_ context
                sig_name = s.group(1)
                rows.append([
                    current_msg["id"],                        # msg_id (0x...)
                    current_msg["name"],                      # msg_name
                    current_msg["frame_type"],                # frame_type
                    current_msg["dlc"],                       # dlc
                    current_msg["comment"],                   # msg_comment
                    sanitize(sig_name),                        # sig_name
                    s.group(2) or "",                         # mode
                    s.group(3),                                # start
                    s.group(4),                                # length
                    "little" if s.group(5) == "1" else "big", # byte_order
                    (s.group(6) == "-"),                      # is_signed (bool)
                    s.group(7),                                # scale
                    s.group(8),                                # offset
                    s.group(9),                                # min
                    s.group(10),                               # max
                    s.group(11),                               # unit
                    sig_comments.get((current_msg["dbc_id"], sig_name), ""),
                ])
    return rows

# ── STEP 3: WRITE CSV (UTF-8 with BOM) ─────────────────────────────────────
def write_csv_rows(rows: List[List[str]], out_path: Path) -> None:
    header = [
        'msg_id','msg_name','frame_type','dlc','msg_comment',
        'sig_name','mode','start','length','byte_order','is_signed',
        'scale','offset','min','max','unit','sig_comment'
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', newline='', encoding='utf-8-sig') as fo:
        writer = csv.writer(fo)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"✅ Wrote {len(rows)} signals → {out_path}")

# ── CSV → DBC HELPERS ─────────────────────────────────────────────────────
def vector_bits(start: int, length: int, byte_order: str) -> List[int]:
    """Return exact bit indices as per Vector numbering."""
    if str(byte_order).lower().startswith('l'):  # Intel / little-endian
        return list(range(start, start + length))
    # Motorola / big-endian: descending bits per byte, jump +8 at byte end
    bits: List[int] = []
    for i in range(length):
        byte_jump = i // 8
        bit = start + 8 * byte_jump - (i % 8)
        bits.append(bit)
    return bits

_true_set = {True, 1, '1', 'true', 't', 'yes', 'y', '-'}
_false_set = {False, 0, '0', 'false', 'f', 'no', 'n', '+'}

def to_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    if s in _true_set:
        return True
    if s in _false_set:
        return False
    # Fallback: any non-empty string except explicit false-like → True
    return s not in ('', 'none', 'nan')

# ── STEP 4: CSV → cantools-compatible DBC ──────────────────────────────────
def csv_to_dbc(csv_path: Path, dbc_out: Path) -> None:
    # Read CSV preserving header
    with csv_path.open('r', encoding='utf-8-sig', newline='') as fi:
        reader = csv.DictReader(fi)
        records = list(reader)

    # Conflict check within same multiplex context
    alloc: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    conflicts: List[Tuple[str, str, str, List[int]]] = []

    for row in records:
        msg_id = row.get('msg_id', '')
        mux_ctx = row.get('mode', '') or 'BASE'
        try:
            start = int(row['start']); length = int(row['length'])
        except Exception:
            # Skip malformed rows
            continue
        bits = vector_bits(start, length, row.get('byte_order', 'little'))
        mode = row.get('mode', '')
        is_mux_def = isinstance(mode, str) and mode.upper().startswith('M') if mode else False
        if not is_mux_def:
            overlap = alloc[msg_id][mux_ctx].intersection(bits)
            if overlap:
                conflicts.append((msg_id, mux_ctx, row.get('sig_name',''), sorted(overlap)))
            alloc[msg_id][mux_ctx].update(bits)
        else:
            alloc[msg_id][mux_ctx].update(bits)

    if conflicts:
        print("⚠️  Genuine bit overlaps detected (same multiplex context):")
        for msg, mux, sig, overlap in conflicts:
            print(f"   – {sig} in message {msg} (ctx {mux}) overlaps bits {overlap}")
        print("   You must fix these rows in the CSV if cantools still rejects them.\n")

    # Group by msg_id
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for r in records:
        grouped[r['msg_id']].append(r)

    # Build DBC lines
    lines: List[str] = [
        'VERSION ""',
        '',
        'NS_ :',
        '    CM_',
        'BS_:',
        ''
    ]

    for msg_id, grp in grouped.items():
        first = grp[0]
        mid = str(msg_id)
        try:
            raw_id = int(mid, 16) if mid.lower().startswith('0x') else int(mid)
        except Exception:
            # Fallback: try hex parse without 0x
            try:
                raw_id = int(mid, 16)
            except Exception:
                print(f"Skipping message with unparseable id: {mid}")
                continue

        frame_type = (first.get('frame_type') or '').strip().lower() or 'standard'
        if raw_id > 0x7FF:
            frame_type = 'extended'
        dbc_id = (raw_id | 0x80000000) if frame_type == 'extended' else raw_id

        try:
            dlc = int(first.get('dlc', 8))
        except Exception:
            dlc = 8

        msg_name = sanitize(first.get('msg_name', f'MSG_{raw_id:X}'))
        msg_comment = first.get('msg_comment', '') or ''

        lines.append(f"BO_ {dbc_id} {msg_name}: {dlc} ECU")

        for row in grp:
            sig_name = sanitize(row.get('sig_name', 'SIG'))
            mode = row.get('mode') or ''
            try:
                start = int(row['start']); length = int(row['length'])
            except Exception:
                continue
            endian = '1' if (row.get('byte_order','little').lower().startswith('l')) else '0'
            sign_char = '-' if to_bool(row.get('is_signed', False)) else '+'

            # scale/offset might be empty; default to 1/0
            try:
                scale = float(row.get('scale', 1) or 1)
            except Exception:
                scale = 1.0
            try:
                offset = float(row.get('offset', 0) or 0)
            except Exception:
                offset = 0.0

            lo = row.get('min', '') or ''
            hi = row.get('max', '') or ''
            unit = row.get('unit', '') or ''

            sg = f"    SG_ {sig_name}"
            if mode:
                sg += f" {mode}"
            sg += f" : {start}|{length}@{endian}{sign_char} ({scale},{offset}) [{lo}|{hi}] \"{unit}\" ECU"
            lines.append(sg)

        lines.append('')
        if msg_comment:
            lines.append(f'CM_ BO_ {dbc_id} "{msg_comment}";')
        for row in grp:
            sc = row.get('sig_comment', '') or ''
            if sc:
                lines.append(f'CM_ SG_ {dbc_id} {sanitize(row.get("sig_name", "SIG"))} "{sc}";')
        lines.append('')

    dbc_out.parent.mkdir(parents=True, exist_ok=True)
    dbc_out.write_text("\n".join(lines), encoding='utf-8')
    print(f"✅  Wrote complete DBC with {sum(len(v) for v in grouped.values())} signals → {dbc_out}")

# ── ORCHESTRATION ──────────────────────────────────────────────────────────
def run_pipeline(in_dbc: Path, out_csv: Path, out_dbc: Path) -> None:
    if not in_dbc.exists():
        raise FileNotFoundError(in_dbc)
    print(f"➡️  Reading DBC: {in_dbc}")

    msg_cmt, sig_cmt = collect_comments(in_dbc)
    rows = parse_dbc_to_rows(in_dbc, msg_cmt, sig_cmt)
    write_csv_rows(rows, out_csv)

    print(f"➡️  Converting CSV → cantools DBC: {out_csv} → {out_dbc}")
    csv_to_dbc(out_csv, out_dbc)

# ── CLI ────────────────────────────────────────────────────────────────────
def parse_args(argv: Iterable[str] | None = None):
    p = argparse.ArgumentParser(description="Convert CSS Electronics/Vector DBC to cantools-compatible DBC via a cleaned CSV")
    p.add_argument('-i', '--in', dest='in_dbc', type=Path, default=DEFAULT_IN_DBC, help='Input DBC file path')
    p.add_argument('-o', '--out', dest='out_dbc', type=Path, default=DEFAULT_OUT_DBC, help='Output cantools-compatible DBC file path')
    p.add_argument('--csv', dest='out_csv', type=Path, default=DEFAULT_OUT_CSV, help='Intermediate CSV path (will be overwritten)')
    return p.parse_args(argv)

if __name__ == '__main__':
    args = parse_args()
    run_pipeline(args.in_dbc, args.out_csv, args.out_dbc)
