import cantools

dbc_path = r"C:\Git_projects\can_diagnostic_tool\data\standardized_full.dbc"

try:
    db = cantools.database.load_file(dbc_path)
    print("✅ DBC file loaded successfully!")
    print(f"Total messages: {len(db.messages)}")

    total_signals = 0
    successful_signals = 0
    failed_signals_info = []

    for msg in db.messages:
        print(f"\n📦 Message: {msg.name} (ID: {hex(msg.frame_id)}, DLC: {msg.length}, Signals: {len(msg.signals)})")
        for sig in msg.signals:
            total_signals += 1
            try:
                # Try accessing all important signal attributes to confirm correct parsing
                _ = sig.name
                _ = sig.start
                _ = sig.length
                _ = sig.byte_order
                _ = sig.is_signed
                _ = sig.scale
                _ = sig.offset
                _ = sig.minimum
                _ = sig.maximum
                _ = sig.unit
                successful_signals += 1
            except Exception as sig_err:
                failed_signals_info.append({
                    "message_name": msg.name,
                    "signal_name": sig.name if 'sig' in locals() and hasattr(sig, 'name') else 'Unknown',
                    "error": str(sig_err)
                })

    print(f"\n✅ Successfully parsed {successful_signals}/{total_signals} signals.")
    if failed_signals_info:
        print(f"\n⚠️ {len(failed_signals_info)} signals failed to parse completely:\n")
        for fail in failed_signals_info:
            print(f"- Message: {fail['message_name']}, Signal: {fail['signal_name']}, Error: {fail['error']}")

except Exception as e:
    print("❌ Failed to load DBC file.")
    print("Error:", e)
