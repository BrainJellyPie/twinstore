"""Joins thin Mach-O executables into one universal (fat) binary, like Apple's `lipo -create`,
so the macOS app can be built on any OS:  python3 tools/lipo.py OUT IN_AMD64 IN_ARM64"""

import struct
import sys

ALIGN = 14  # slices start on 16 KiB boundaries, as lipo does for x86_64 and arm64


def main(out: str, *thin: str) -> None:
    slices = []
    for path in thin:
        data = open(path, "rb").read()
        magic, cputype, cpusubtype = struct.unpack("<III", data[:12])
        if magic != 0xFEEDFACF:
            sys.exit(f"{path}: not a 64-bit Mach-O executable")
        slices.append((cputype, cpusubtype, data))
    header = struct.pack(">II", 0xCAFEBABE, len(slices))
    offset = 1 << ALIGN
    entries, body = b"", b""
    for cputype, cpusubtype, data in slices:
        entries += struct.pack(">IIIII", cputype, cpusubtype, offset, len(data), ALIGN)
        pad = (-(offset + len(data))) % (1 << ALIGN)
        body += data + b"\0" * pad
        offset += len(data) + pad
    head = header + entries
    with open(out, "wb") as f:
        f.write(head + b"\0" * ((1 << ALIGN) - len(head)) + body)


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
