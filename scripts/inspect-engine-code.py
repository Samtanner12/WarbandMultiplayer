"""Offline disassembly of the pinned executables; never modifies binaries."""
import argparse
from pathlib import Path
import sys
import struct
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/research-python'))
import capstone
import pefile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('exe')
parser.add_argument('--start', type=lambda v:int(v, 0))
parser.add_argument('--size', type=lambda v:int(v, 0), default=0x300)
parser.add_argument('--string')
args = parser.parse_args()
pe = pefile.PE(args.exe)
base = pe.OPTIONAL_HEADER.ImageBase
mapped = pe.get_memory_mapped_image()
decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
if args.string:
    needle = args.string.encode('ascii') + b'\0'
    offset = mapped.find(needle)
    if offset < 0: raise SystemExit('String not found')
    target = base + offset
    print('String VA: 0x%08X' % target)
    for section in pe.sections:
        if section.Characteristics & 0x20000000:
            content = section.get_data()
            position = content.find(struct.pack('<I', target))
            while position >= 0:
                print('Address operand at VA: 0x%08X' % (base + section.VirtualAddress + position))
                position = content.find(struct.pack('<I', target), position + 4)
else:
    if args.start is None: parser.error('--start or --string is required')
    for instruction in decoder.disasm(mapped[args.start-base:args.start-base+args.size], args.start):
        print('0x%08X %-8s %s' % (instruction.address, instruction.mnemonic, instruction.op_str))
