import pandas as pd
import os

# Input and output file paths
input_csv_path = r"C:\Git_projects\can_diagnostic_tool\data\signals.csv"
output_dbc_path = r"C:\Git_projects\can_diagnostic_tool\data\generated_from_signals.dbc"

# Load the CSV
signals_df = pd.read_csv(input_csv_path)

# Default values for missing fields
DEFAULTS = {
    "mode": "",
    "sig_comment": "",
    "unit": "",
}

# Helper function to convert byte order to DBC format
def get_byte_order(byte_order):
    return "0" if byte_order == "little" else "1"

# DBC header lines
dbc_lines = [
    'VERSION "Generated from signals.csv"\n\n',
    "NS_ :\n"
    "\tNS_DESC_\n\tCM_\n\tBA_DEF_\n\tBA_\n\tVAL_\n\tCAT_DEF_\n\tCAT_\n\tFILTER\n"
    "\tBA_DEF_DEF_\n\tEV_DATA_\n\tENVVAR_DATA_\n\tSGTYPE_\n\tSGTYPE_VAL_\n"
    "\tBA_DEF_SGTYPE_\n\tBA_SGTYPE_\n\tSIG_TYPE_REF_\n\tVAL_TABLE_\n\tSIG_GROUP_\n"
    "\tSIG_VALTYPE_\n\tSIGTYPE_VALTYPE_\n\tBO_TX_BU_\n\tBA_DEF_REL_\n\tBA_REL_\n"
    "\tBA_DEF_DEF_REL_\n\tBU_SG_REL_\n\tBU_EV_REL_\n\tBU_BO_REL_\n\tSG_MUL_VAL_\n\n",
    "BS_:\n\n",
    "BU_: Vector__XXX\n\n"
]

# Group signals by message ID and write BO_ and SG_ entries
for msg_id, group in signals_df.groupby("msg_id"):
    msg_name = group["msg_name"].iloc[0]
    dlc = group["dlc"].iloc[0]
    msg_comment = group["msg_comment"].iloc[0] if pd.notnull(group["msg_comment"].iloc[0]) else ""
    frame_type = group["frame_type"].iloc[0]
    frame_flag = "EXT_" if frame_type == "extended" else ""

    dbc_lines.append(f"BO_ {int(msg_id, 16)} {msg_name}: {dlc} Vector__XXX\n")

    for _, row in group.iterrows():
        sig_name = row["sig_name"]
        start = int(row["start"])
        length = int(row["length"])
        byte_order = get_byte_order(row["byte_order"])
        is_signed = "-" if row["is_signed"] else "+"
        scale = row["scale"]
        offset = row["offset"]
        min_val = row["min"]
        max_val = row["max"]
        unit = row["unit"] if pd.notnull(row["unit"]) else DEFAULTS["unit"]

        dbc_lines.append(
            f" SG_ {sig_name} : {start}|{length}@{byte_order}{is_signed} "
            f"({scale},{offset}) [{min_val}|{max_val}] \"{unit}\" Vector__XXX\n"
        )

    if msg_comment:
        dbc_lines.append(f'CM_ BO_ {int(msg_id, 16)} "{msg_comment}";\n')

    for _, row in group.iterrows():
        sig_comment = row["sig_comment"] if pd.notnull(row["sig_comment"]) else DEFAULTS["sig_comment"]
        if sig_comment:
            dbc_lines.append(
                f'CM_ SG_ {int(msg_id, 16)} {row["sig_name"]} "{sig_comment}";\n'
            )

# Save the DBC file
with open(output_dbc_path, "w", encoding="utf-8") as f:
    f.writelines(dbc_lines)

print(f"DBC file successfully generated at: {output_dbc_path}")
