def inspect_first_bytes(path):
    print(f"=== Inspecting first bytes of {path} ===")
    try:
        with open(path, "rb") as f:
            data = f.read(32)
            print("First 32 bytes (hex):", data.hex())
            print("First byte (dec):", data[0])
    except Exception as e:
        print("Error:", e)
    print("-" * 50)

inspect_first_bytes("/Users/juanluisgrandi/AI/MP/CLIENTESPA.DBI")
inspect_first_bytes("/Users/juanluisgrandi/AI/MP/data/Clientes_web.dbi")
