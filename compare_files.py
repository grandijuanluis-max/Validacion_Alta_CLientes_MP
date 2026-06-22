import os

file_working = "/Users/juanluisgrandi/AI/MP/F:\\Clientes\\Pasina\\EXPORTACIONES\\Validador\\Importa/domicilios_entrega.txt"
file_new = "/Users/juanluisgrandi/AI/MP/data/domicilios_entrega.txt"

def compare(path1, path2):
    print(f"Comparing {path1} and {path2}...")
    if not os.path.exists(path1):
        print(f"File 1 does not exist: {path1}")
        return
    if not os.path.exists(path2):
        print(f"File 2 does not exist: {path2}")
        return
        
    with open(path1, "rb") as f1, open(path2, "rb") as f2:
        d1 = f1.read()
        d2 = f2.read()
        
    print(f"Size of file 1: {len(d1)}")
    print(f"Size of file 2: {len(d2)}")
    
    if d1 == d2:
        print("FILES ARE IDENTICAL BYTE-BY-BYTE!")
        return
        
    max_len = max(len(d1), len(d2))
    diffs = 0
    for i in range(max_len):
        b1 = d1[i] if i < len(d1) else None
        b2 = d2[i] if i < len(d2) else None
        if b1 != b2:
            diffs += 1
            if diffs <= 20:
                print(f"Diff at byte {i} (hex {hex(i)}): file1={hex(b1) if b1 is not None else 'None'} | file2={hex(b2) if b2 is not None else 'None'}")
    print(f"Total different bytes: {diffs}")

if __name__ == "__main__":
    compare(file_working, file_new)
