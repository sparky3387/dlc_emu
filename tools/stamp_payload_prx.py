#!/usr/bin/env python3
"""Finalize SCE identity and .dynstr offsets on an LLD-linked PRX.

Three things only this step can do:

  * point every SCE dynamic entry at its name in .dynstr, which did not exist
    when the linker script was written;
  * set e_type to ET_SCE_DYNAMIC and the FreeBSD ABI bytes;
  * zero p_memsz on the unloadable segments. `(INFO)` in the linker script
    gets p_vaddr to 0 but lld still derives p_memsz from p_filesz, and a
    segment that is not loaded may not claim address space -- the loader
    refuses the whole module with "illegal segment header" if it does, one
    segment at a time.

    Only the segments at p_vaddr 0 are unloadable. The build-id PT_NOTE sits
    inside a PT_LOAD and keeps its size in the Prospero-built module, as does
    PT_SCE_LIBVERSION, which is at p_vaddr 0 and is left alone deliberately.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

PT_NOTE = 4
PT_SCE_COMMENT = 0x6FFFFF00

# Tags whose value carries a .dynstr offset in its low 32 bits.
NAMED_TAGS = {
    0x61000045,  # DT_SCE_NEEDED_MODULE
    0x61000049,  # DT_SCE_IMPORT_LIB
    0x61000043,  # DT_SCE_MODULE_INFO
    0x61000041,  # DT_SCE_MODULE_FILENAME
    0x61000047,  # DT_SCE_EXPORT_LIB
}


def sections(data: bytes) -> dict[str, tuple[int, int, int]]:
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    if shentsize < 64 or shoff + shentsize * shnum > len(data):
        raise ValueError("invalid ELF section table")
    raw = [
        struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize)
        for i in range(shnum)
    ]
    if not 0 <= shstrndx < len(raw):
        raise ValueError("invalid ELF section-name table index")
    header = raw[shstrndx]
    names = data[header[4] : header[4] + header[5]]
    result = {}
    for entry in raw:
        end = names.find(b"\0", entry[0])
        name = names[entry[0] : end].decode("ascii") if end >= 0 else ""
        result[name] = (entry[4], entry[5], entry[9])
    return result


def dynstr_offset(data: bytes, offset: int, size: int, name: str) -> int:
    """Exact-entry lookup: a plain find would match 'libSceAppContent' inside
    'libSceAppContentIro' and point two dynamic entries at one string."""
    needle = name.encode("ascii") + b"\0"
    table = data[offset : offset + size]
    matches = []
    start = 0
    while True:
        found = table.find(needle, start)
        if found < 0:
            break
        if found == 0 or table[found - 1] == 0:
            matches.append(found)
        start = found + 1
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one .dynstr entry for {name!r}, found {len(matches)}"
        )
    return matches[0]


def zero_unloadable_memsz(data: bytearray) -> int:
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    zeroed = 0
    for index in range(phnum):
        base = phoff + index * phentsize
        ptype = struct.unpack_from("<I", data, base)[0]
        vaddr = struct.unpack_from("<Q", data, base + 0x10)[0]
        if ptype not in (PT_NOTE, PT_SCE_COMMENT) or vaddr:
            continue
        memsz_at = base + 0x28
        if struct.unpack_from("<Q", data, memsz_at)[0]:
            struct.pack_into("<Q", data, memsz_at, 0)
            zeroed += 1
    return zeroed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prx", type=Path)
    parser.add_argument("--meta-json", type=Path, required=True)
    args = parser.parse_args()

    meta = json.loads(args.meta_json.read_text())
    data = bytearray(args.prx.read_bytes())
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01":
        raise ValueError("expected a little-endian ELF64 image")
    if struct.unpack_from("<H", data, 0x10)[0] != 3:
        raise ValueError("LLD output is not ET_DYN")
    if struct.unpack_from("<H", data, 0x38)[0] != 14:
        raise ValueError("LLD output does not have the PRX program-header layout")

    section_map = sections(data)
    dynstr = section_map.get(".dynstr")
    dynamic = section_map.get(".dynamic")
    if dynstr is None or dynamic is None or dynamic[2] < 16:
        raise ValueError("LLD output lacks the PRX dynamic sections")

    offsets = {
        name: dynstr_offset(data, dynstr[0], dynstr[1], name)
        for name in meta["dynstr_names"]
    }

    # The generated entries are in .dynamic in exactly the order the linker
    # script emitted them, so walking both in step assigns each its own name.
    expected = [entry for entry in meta["dynamic"] if entry["name"] is not None]
    seen = 0
    for entry_offset in range(dynamic[0], dynamic[0] + dynamic[1], dynamic[2]):
        tag, value = struct.unpack_from("<QQ", data, entry_offset)
        if tag not in NAMED_TAGS:
            continue
        if seen >= len(expected):
            raise ValueError("more named SCE dynamic entries than the metadata has")
        entry = expected[seen]
        if entry["tag"] != tag:
            raise ValueError(
                f"SCE dynamic entry {seen} is {tag:#x}, metadata says {entry['tag']:#x}"
            )
        struct.pack_into(
            "<Q",
            data,
            entry_offset + 8,
            (value & 0xFFFFFFFF00000000) | offsets[entry["name"]],
        )
        seen += 1
    if seen != len(expected):
        raise ValueError(
            f"patched {seen} named SCE dynamic entries, metadata has {len(expected)}"
        )

    zeroed = zero_unloadable_memsz(data)

    data[7] = 9  # ELFOSABI_FREEBSD
    data[8] = 2  # EI_ABIVERSION
    struct.pack_into("<H", data, 0x10, 0xFE18)  # ET_SCE_DYNAMIC
    args.prx.write_bytes(data)
    print(
        f"stamped {meta['target']}: {seen} dynamic names, "
        f"{zeroed} unloadable segment memsz zeroed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
