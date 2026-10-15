"""Read the pinned WSE2 v2 dictionary format without modifying a save."""
import argparse, json, struct
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('path',type=Path)
parser.add_argument('--prefix',action='append',default=[])
args=parser.parse_args()
data=args.path.read_bytes()
if len(data)>4*1024*1024 or len(data)<12:raise SystemExit('Invalid dictionary length')
magic,version,count=struct.unpack_from('<4sII',data)
if magic!=b'DESW' or version!=2 or count>65536:raise SystemExit('Unsupported dictionary header')
result={};offset=12
for unused in range(count):
    if offset+8>len(data):raise SystemExit('Truncated dictionary entry')
    key_size,value_size=struct.unpack_from('<II',data,offset);offset+=8
    if offset+key_size+value_size>len(data):raise SystemExit('Truncated dictionary value')
    key=data[offset:offset+key_size].decode('utf-8');offset+=key_size
    value=data[offset:offset+value_size].decode('utf-8');offset+=value_size
    if not args.prefix or any(key.startswith(p) for p in args.prefix):result[key]=value
if offset!=len(data):raise SystemExit('Unexpected dictionary trailer')
print(json.dumps(result,indent=2,sort_keys=True))
