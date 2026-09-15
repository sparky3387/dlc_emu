#!/usr/bin/env python3
"""Audit the payload-SDK PRX modules against the .pemd files they came from.

The build has no step that can fail loudly when a NID, a library id or a
dynamic entry comes out wrong: an incorrect id links cleanly and only misbehaves
on the console. This reads the finished module back and checks it against the
same .pemd the Prospero linker would have read.
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

from dlc_prx_meta import IMPORT_MODULES, export_nid, name_to_nid, parse_pemd
from prx_hash_fix import Elf64LE, buckets_to_symbol_map, elf_hash

DT_NEEDED = 1
DT_SONAME = 14
DT_SCE_MODULE_FILENAME = 0x61000041
DT_SCE_MODULE_INFO = 0x61000043
DT_SCE_NEEDED_MODULE = 0x61000045
DT_SCE_EXPORT_LIB = 0x61000047
DT_SCE_IMPORT_LIB = 0x61000049

IMPORT_RE = re.compile(r"^[A-Za-z0-9+\-]{11}#[A-Za-z0-9+\-]#[A-Za-z0-9+\-]$")

# What ps5/prx/prx.script produces. The Prospero-built module carries the same
# fourteen segments in a different order, which the loader does not mind -- it
# finds each by type, and the PT_LOADs are still in ascending p_vaddr. What it
# does mind is a segment list that is missing one, so check the multiset too.
EXPECTED_PHDR_TYPES = [
    1, 1, 1, 0x6474E552, 1, 0x61000002, 2, 7,
    0x6474E550, 1, 0x6FFFFF00, 0x6FFFFF01, 4, 4,
]
REFERENCE_PHDR_TYPES = [
    1, 1, 0x6474E550, 1, 0x6474E552, 7, 0x61000002, 1,
    1, 4, 2, 0x6FFFFF00, 0x6FFFFF01, 4,
]

PT_NOTE = 4
PT_SCE_COMMENT = 0x6FFFFF00

# What ps5/crt emits, byte for byte. These are the CRT's whole contribution to
# the module's SCE identity, so a change here is worth failing over.
EXPECTED_MODULE_PARAM = bytes.fromhex(
    "2000000000000000 bff4133c03000000 0100050809000002 0100000000000000".replace(" ", "")
)
EXPECTED_SCEVERSION = bytes.fromhex(
    "0000160008637274693a02000009000000010200000900000001"
    "00001b0008637274626567696e533a02000009000000010200000900000001"
    "0000190008637274656e64533a02000009000000010200000900000001"
    "00001600086372746e3a02000009000000010200000900000001"
)

FSELF_MAGIC = b"\x4f\x15\x3d\x1d"


class VerifyError(ValueError):
    pass


def fself_versions(data: bytes) -> tuple[int, int]:
    common_header_size = struct.calcsize("<4s4B")
    extended_header_size = struct.calcsize("<I2HQ2H4x")
    if data[:4] != FSELF_MAGIC:
        raise VerifyError("SPRX is not a fake signed ELF image")
    _, _, _, _, num_entries, _ = struct.unpack_from(
        "<I2HQ2H4x", data, common_header_size
    )
    elf_offset = common_header_size + extended_header_size + num_entries * 32
    if data[elf_offset:elf_offset + 4] != b"\x7fELF":
        raise VerifyError("SPRX does not contain an ELF header where expected")
    phoff = struct.unpack_from("<Q", data, elf_offset + 0x20)[0]
    ehsize, phentsize, phnum = struct.unpack_from("<HHH", data, elf_offset + 0x34)
    header_size = max(ehsize, phoff + phentsize * phnum)
    ex_info_offset = elf_offset + ((header_size + 15) & ~15)
    _, _, app_version, fw_version = struct.unpack_from("<4Q", data, ex_info_offset)
    return app_version, fw_version


def read_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def check_identity(data: bytes) -> None:
    if data[:4] != b"\x7fELF" or data[7] != 9 or data[8] != 2:
        raise VerifyError("PRX is not an ELF64 FreeBSD ABI v2 image")
    if struct.unpack_from("<H", data, 0x10)[0] != 0xFE18:
        raise VerifyError("PRX e_type is not ET_SCE_DYNAMIC (0xfe18)")
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    if phentsize < 56 or phnum != len(EXPECTED_PHDR_TYPES):
        raise VerifyError(f"unexpected PRX program-header count: {phnum}")
    types = [
        struct.unpack_from("<I", data, phoff + index * phentsize)[0]
        for index in range(phnum)
    ]
    if types != EXPECTED_PHDR_TYPES:
        raise VerifyError(f"PRX program-header layout mismatch: {types}")
    if sorted(types) != sorted(REFERENCE_PHDR_TYPES):
        raise VerifyError("PRX segment list differs from the Prospero module's")

    loads = []
    for index in range(phnum):
        base = phoff + index * phentsize
        ptype, _flags, _off, vaddr = struct.unpack_from("<IIQQ", data, base)
        memsz = struct.unpack_from("<Q", data, base + 0x28)[0]
        if ptype == 1:
            loads.append(vaddr)
        # An unloadable segment that claims address space is refused outright,
        # one segment at a time, before anything else about the module is read.
        if ptype in (PT_NOTE, PT_SCE_COMMENT) and not vaddr and memsz:
            raise VerifyError(
                f"unloadable segment {index} still claims {memsz:#x} bytes"
            )
    if loads != sorted(loads):
        raise VerifyError(f"PT_LOAD segments are not in address order: {loads}")


def check_crt(elf: Elf64LE, data: bytes) -> None:
    module_param = elf.section(".sce_module_param")
    actual = data[module_param.offset:module_param.offset + module_param.size]
    if actual != EXPECTED_MODULE_PARAM:
        raise VerifyError(f"unexpected .sce_module_param: {actual.hex()}")
    sceversion = elf.section(".sceversion")
    actual = data[sceversion.offset:sceversion.offset + sceversion.size]
    if actual != EXPECTED_SCEVERSION:
        raise VerifyError(f"unexpected .sceversion records: {actual.hex()}")
    if not elf.section(".init").size or not elf.section(".fini").size:
        raise VerifyError("CRT did not emit _init/_fini sections")


def check_hash_correction(linked: bytes, fixed: bytes, elf: Elf64LE) -> int:
    if len(linked) != len(fixed):
        raise VerifyError("hash correction changed the PRX size")
    section = elf.section(".hash")
    changed = [
        index for index, (a, b) in enumerate(zip(linked, fixed)) if a != b
    ]
    if not changed:
        raise VerifyError("hash correction did not change the linked PRX")
    escaped = [
        index for index in changed
        if not section.offset <= index < section.offset + section.size
    ]
    if escaped:
        raise VerifyError(f"hash correction changed byte outside .hash: {escaped[0]:#x}")
    return len(changed)


def verify_module(target: str, out: Path, pemd_dir: Path, fself_version: int) -> str:
    meta = parse_pemd(pemd_dir / f"{target}.pemd", target)
    generated = out / "obj" / target / "generated"
    fixed = (out / f"{target}.prx").read_bytes()
    linked = (out / "obj" / target / "link" / f"{target}.prx").read_bytes()

    app_version, fw_version = fself_versions((out / f"{target}.sprx").read_bytes())
    if app_version != fself_version or fw_version != fself_version:
        raise VerifyError(
            f"unexpected FSELF versions: app={app_version:#010x} "
            f"fw={fw_version:#010x} expected={fself_version:#010x}"
        )

    check_identity(fixed)
    elf = Elf64LE(fixed)
    check_crt(elf, fixed)
    changed_bytes = check_hash_correction(linked, fixed, elf)

    dynstr = elf.section(".dynstr")
    entries = elf.dynamic_entries()
    needed, sonames, modules, libraries, filenames = [], [], {}, {}, []
    for tag, value in entries:
        if tag == DT_NEEDED:
            needed.append(elf.str_at(dynstr, value))
        elif tag == DT_SONAME:
            sonames.append(elf.str_at(dynstr, value))
        elif tag == DT_SCE_MODULE_INFO:
            modules[(value >> 48) & 0xFFFF] = elf.str_at(dynstr, value & 0xFFFFFFFF)
        elif tag == DT_SCE_EXPORT_LIB:
            libraries[(value >> 48) & 0xFFFF] = elf.str_at(dynstr, value & 0xFFFFFFFF)
        elif tag == DT_SCE_MODULE_FILENAME:
            filenames.append(elf.str_at(dynstr, value & 0xFFFFFFFF))

    expected_needed = [f"{name}.prx" for name in IMPORT_MODULES]
    if needed != expected_needed or sonames:
        raise VerifyError(f"unexpected needed={needed} soname={sonames}")
    if filenames != [meta.soname]:
        raise VerifyError(f"unexpected DT_SCE_MODULE_FILENAME: {filenames}")
    if modules != {0: meta.module}:
        raise VerifyError(f"unexpected module info entries: {modules}")
    expected_libraries = {lib.library_id: lib.name for lib in meta.libraries}
    if libraries != expected_libraries:
        raise VerifyError(
            f"export library ids wrong: got={libraries} want={expected_libraries}"
        )

    # Every imported module must be both DT_SCE_NEEDED_MODULE and
    # DT_SCE_IMPORT_LIB at its own id, or an import resolves against the
    # wrong library at load time.
    sce_needed = {
        (value >> 48) & 0xFFFF: elf.str_at(dynstr, value & 0xFFFFFFFF)
        for tag, value in entries if tag == DT_SCE_NEEDED_MODULE
    }
    sce_imports = {
        (value >> 48) & 0xFFFF: elf.str_at(dynstr, value & 0xFFFFFFFF)
        for tag, value in entries if tag == DT_SCE_IMPORT_LIB
    }
    want_needed = {index + 1: name for index, name in enumerate(IMPORT_MODULES)}
    want_imports = {index: name for index, name in enumerate(IMPORT_MODULES)}
    if sce_needed != want_needed or sce_imports != want_imports:
        raise VerifyError(
            f"import ids wrong: needed={sce_needed} import_lib={sce_imports}"
        )

    expected_exports = {symbol for _name, symbol, _lib in meta.exports()}
    dynsyms = elf.dynsyms()
    defined = {sym.name for sym in dynsyms[1:] if sym.st_shndx != 0 and sym.name}
    actual_exports = {name for name in defined if IMPORT_RE.fullmatch(name)}
    missing = sorted(expected_exports - actual_exports)
    extra = sorted(actual_exports - expected_exports)
    if missing or extra:
        raise VerifyError(f"export mismatch: missing={missing} extra={extra}")

    # The marker symbols exist only to put names in .dynstr. Anything else
    # defined in .dynsym is a leak out of the module's intended surface.
    allowed = expected_exports | set(meta.dynstr_names())
    leaked = sorted(defined - allowed)
    missing_markers = sorted(set(meta.dynstr_names()) - defined)
    if leaked or missing_markers:
        raise VerifyError(
            f"dynamic definitions wrong: extra={leaked} missing={missing_markers}"
        )

    imports = [sym.name for sym in dynsyms[1:] if sym.st_shndx == 0 and sym.name]
    plain = sorted(name for name in imports if not IMPORT_RE.fullmatch(name))
    if plain:
        raise VerifyError(f"plain or malformed imports remain: {plain}")
    for module_name in IMPORT_MODULES:
        suffix = meta.import_suffix(module_name)
        names = read_list(generated / f"{module_name}.imports.txt")
        want = {f"{name_to_nid(name)}{suffix}" for name in names}
        got = {name for name in imports if name.endswith(suffix)}
        if want != got:
            raise VerifyError(
                f"{module_name} import mismatch: "
                f"missing={sorted(want - got)} extra={sorted(got - want)}"
            )

    # The loader looks an export up by hashing "<nid>#<library>#<module>"; lld
    # hashed the short literal name. Confirm every export ended up where the
    # loader will look for it.
    _, nbucket, _, buckets, chains = elf.hash_table()
    actual_buckets = buckets_to_symbol_map(buckets, chains)
    groups = elf.export_groups()
    wrong = []
    for sym in dynsyms[1:]:
        if sym.name not in actual_exports or sym.nid_parts is None:
            continue
        nid, library_id, module_id = sym.nid_parts
        group = groups[(library_id, module_id)]
        want_bucket = elf_hash(group.canonical(nid)) % nbucket
        if actual_buckets.get(sym.index) != want_bucket:
            wrong.append((sym.name, actual_buckets.get(sym.index), want_bucket))
    if wrong:
        raise VerifyError(f"incorrect export hash buckets: {wrong}")

    # Two names colliding inside one library would silently drop an export:
    # the second symbol overwrites the first and the NID diff still passes.
    for library in meta.libraries:
        nids = {export_nid(name) for name in library.functions}
        if len(nids) != len(library.functions):
            raise VerifyError(f"NID collision inside {library.name}")

    return (
        f"{target}: ok module={meta.module} exports={len(actual_exports)} "
        f"libs={len(meta.libraries)}@{meta.libraries[0].library_id}.."
        f"{meta.libraries[-1].library_id} imports={len(imports)} "
        f"buckets={nbucket} hash_changed_bytes={changed_bytes} "
        f"fself=0x{fw_version:08x}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("out/payload-sdk"))
    parser.add_argument("--pemd-dir", type=Path, default=Path("msbuild/pemd"))
    parser.add_argument("--modules", nargs="+", required=True)
    parser.add_argument(
        "--fself-version", type=lambda value: int(value, 0), default=0x02000001
    )
    args = parser.parse_args()

    for target in args.modules:
        print(verify_module(target, args.out, args.pemd_dir, args.fself_version))
    print(f"payload_prx_ok modules={len(args.modules)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
