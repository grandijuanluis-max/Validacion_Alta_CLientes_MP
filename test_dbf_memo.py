import dbf
import os

path = "/Users/juanluisgrandi/AI/MP/test_memo.dbi"
if os.path.exists(path):
    os.remove(path)
memo_path = path.replace(".dbi", ".fpt")
if os.path.exists(memo_path):
    os.remove(memo_path)

schema = "CODIGO N(6,0); NOMBRE C(30); NOTAS M"
table = dbf.Table(path, schema, dbf_type='fp', codepage='cp1252')
table.open(mode=dbf.READ_WRITE)
table.append((1, "TEST", "This is a memo note"))
table.close()

print("Files created:")
for ext in [".dbi", ".fpt", ".dbt"]:
    p = "/Users/juanluisgrandi/AI/MP/test_memo" + ext
    if os.path.exists(p):
        print(f"  {ext}: size={os.path.getsize(p)} bytes")
