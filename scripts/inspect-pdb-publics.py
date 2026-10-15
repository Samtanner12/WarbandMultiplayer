"""Read MSF7/CodeView public symbols; no process access or binary changes."""
from pathlib import Path
import argparse
import json
import re
import struct

def publics(pdb_path, exe_path):
    data = Path(pdb_path).read_bytes()
    if not data.startswith(b'Microsoft C/C++ MSF 7.00'):
        raise ValueError('Expected an MSF7 PDB')
    block_size, _, _, directory_size, _, block_map = struct.unpack_from('<6I', data, 32)
    blocks = struct.unpack_from('<%dI' % ((directory_size + block_size - 1)//block_size), data, block_map*block_size)
    directory = b''.join(data[b*block_size:(b+1)*block_size] for b in blocks)[:directory_size]
    count, = struct.unpack_from('<I', directory)
    sizes = struct.unpack_from('<%dI' % count, directory, 4)
    position = 4 + count*4
    streams = []
    for size in sizes:
        if size == 0xffffffff:
            streams.append(b''); continue
        n = (size + block_size - 1)//block_size
        indices = struct.unpack_from('<%dI' % n, directory, position)
        position += n*4
        streams.append(b''.join(data[b*block_size:(b+1)*block_size] for b in indices)[:size])
    symbol_stream, = struct.unpack_from('<H', streams[3], 20)
    exe = Path(exe_path).read_bytes()
    pe_offset, = struct.unpack_from('<I', exe, 60)
    section_count, = struct.unpack_from('<H', exe, pe_offset + 6)
    optional_size, = struct.unpack_from('<H', exe, pe_offset + 20)
    image_base, = struct.unpack_from('<I', exe, pe_offset + 24 + 28)
    section_start = pe_offset + 24 + optional_size
    sections = [struct.unpack_from('<I', exe, section_start + i*40 + 12)[0] for i in range(section_count)]
    symbols = streams[symbol_stream]
    offset = 0
    result = []
    while offset + 4 <= len(symbols):
        length, kind = struct.unpack_from('<HH', symbols, offset)
        if length < 2 or offset + 2 + length > len(symbols):
            raise ValueError('Invalid CodeView symbol record')
        if kind == 0x110e: # S_PUB32
            flags, displacement, section = struct.unpack_from('<IIH', symbols, offset + 4)
            name = symbols[offset + 14:offset + length + 2].split(b'\0', 1)[0].decode('utf-8', errors='replace')
            if 1 <= section <= len(sections):
                result.append({'name':name, 'va':image_base + sections[section-1] + displacement, 'flags':flags})
        offset += length + 2
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdb'); parser.add_argument('exe')
    parser.add_argument('--filter', default='.*')
    parser.add_argument('--output')
    args = parser.parse_args()
    records = publics(args.pdb, args.exe)
    if args.output:
        Path(args.output).write_text(json.dumps(records, indent=2), encoding='utf-8')
    for record in records:
        if re.search(args.filter, record['name'], re.I):
            print('0x%08X %s' % (record['va'], record['name']))
