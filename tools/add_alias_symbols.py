#!/usr/bin/env python3
"""Give a function a second NID name, for exports listed under two libraries.

A .pemd may list one function under more than one library -- sceAppContent and
sceAppContentGameTrials both export sceAppContentGetGameTrialsFlag. That is one
function with two NIDs, and the Prospero linker emits two dynamic symbols at
the same address.

objcopy --redefine-sym can only rename the definition once, and an assembler
`.set` cannot alias a symbol defined in a different object -- the alias comes
out undefined and the link fails on the version script. Adding the symbol to
the object that already has the definition is the one route that produces a
real global function symbol at the right address.
"""

from __future__ import annotations

import argparse
import struct
import subprocess
from pathlib import Path


def read_symbols(path: Path) -> dict[str, tuple[str, int]]:
    """{symbol: (section name, value)} for every defined symbol in an object."""
    data = path.read_bytes()
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError(f"{path}: expected a little-endian ELF64 object")
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    headers = [
        struct.unpack_from("<IIQQQQIIQQ", data, shoff + index * shentsize)
        for index in range(shnum)
    ]
    shstr = headers[shstrndx]

    def string(table_offset: int, table_size: int, offset: int) -> str:
        start = table_offset + offset
        end = data.find(b"\0", start, table_offset + table_size)
        return data[start:end].decode("ascii")

    names = [string(shstr[4], shstr[5], header[0]) for header in headers]

    result: dict[str, tuple[str, int]] = {}
    for header in headers:
        if header[1] != 2:  # SHT_SYMTAB
            continue
        strtab = headers[header[6]]
        entsize = header[9] or 24
        for offset in range(header[4], header[4] + header[5], entsize):
            st_name, _info, _other, st_shndx, st_value, _size = struct.unpack_from(
                "<IBBHQQ", data, offset
            )
            if not st_name or st_shndx == 0 or st_shndx >= len(headers):
                continue
            result[string(strtab[4], strtab[5], st_name)] = (
                names[st_shndx],
                st_value,
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("objects", nargs="+", type=Path)
    parser.add_argument("--aliases", type=Path, required=True)
    parser.add_argument("--objcopy", required=True)
    args = parser.parse_args()

    wanted = []
    for line in args.aliases.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        alias, primary = line.split("\t")
        wanted.append((alias, primary))
    if not wanted:
        print("no export aliases for this module")
        return 0

    tables = {path: read_symbols(path) for path in args.objects}

    added = 0
    for path, symbols in tables.items():
        arguments = []
        for alias, primary in wanted:
            if primary not in symbols or alias in symbols:
                continue
            section, value = symbols[primary]
            arguments.append(
                f"--add-symbol={alias}={section}:{value:#x},global,function"
            )
        if arguments:
            subprocess.run([args.objcopy, *arguments, str(path)], check=True)
            added += len(arguments)

    # An alias whose primary is nowhere would leave the version script asking
    # the linker to export a symbol that does not exist -- report it here,
    # where the cause is obvious, rather than as a link failure.
    unplaced = [
        alias
        for alias, primary in wanted
        if not any(primary in symbols or alias in symbols for symbols in tables.values())
    ]
    if unplaced:
        raise ValueError(f"no object defines the primary for aliases: {unplaced}")

    print(f"aliased {added} export symbol(s) across {len(tables)} object(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
