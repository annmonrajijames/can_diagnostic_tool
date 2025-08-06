import cantools
import csv

dbc_path = r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.dbc"
csv_output_path = r"C:\Git_projects\can_diagnostic_tool\data\DBC_sample_cantools.csv"

try:
    db = cantools.database.load_file(dbc_path)
    print("✅ DBC file loaded successfully!")
    print(f"Total messages: {len(db.messages)}")

    total_signals = 0

    with open(csv_output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Message_Name", "Message_ID", "Message_DLC", "Message_Comment",
            "Signal_Name", "Start_Bit", "Signal_Length", "Byte_Order",
            "Is_Signed", "Factor", "Offset", "Minimum", "Maximum", "Unit",
            "Signal_Comment", "Signal_Multiplexer_Indicator",
            "Signal_Multiplexer_Value", "Signal_Receiver",
            "Signal_Is_Float", "Signal_Choices"
        ])

        for msg in db.messages:
            for sig in msg.signals:
                total_signals += 1

                if sig.is_multiplexer:
                    multiplexer_type = "Multiplexor"
                    multiplexer_value = ""
                elif sig.multiplexer_ids is not None:
                    multiplexer_type = "Multiplexed Signal"
                    multiplexer_value = ', '.join(map(str, sig.multiplexer_ids))
                else:
                    multiplexer_type = ""
                    multiplexer_value = ""

                writer.writerow([
                    msg.name,
                    hex(msg.frame_id),
                    msg.length,
                    msg.comment if msg.comment else "",
                    sig.name,
                    sig.start,
                    sig.length,
                    sig.byte_order,
                    sig.is_signed,
                    sig.scale,
                    sig.offset,
                    sig.minimum,
                    sig.maximum,
                    sig.unit,
                    sig.comment if sig.comment else "",
                    multiplexer_type,
                    multiplexer_value,
                    ', '.join(sig.receivers) if sig.receivers else "",
                    sig.is_float,
                    str(sig.choices) if sig.choices else ""
                ])

    print(f"✅ Total signals: {total_signals}")
    print(f"📄 Full signal data exported to CSV:\n{csv_output_path}")

except Exception as e:
    print("❌ Failed to load or export DBC.")
    print("Error:", e)
