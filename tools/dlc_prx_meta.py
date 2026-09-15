#!/usr/bin/env python3
"""The one place the PRX identity arithmetic lives.

A .pemd is the authoritative description of a dlc_emu module: it names the
module and every library it exports, and the Prospero linker reads it on the
Windows route. The payload-SDK route has no reader for it, so this module
parses it and derives everything the Linux link needs -- NIDs, symbol suffixes,
library ids and the SCE dynamic entries -- from that same file.

WHY THIS IS ONE MODULE AND NOT THREE COPIES. The generator, the linker-script
preparer and the post-link stamper must agree on every id exactly. Get an id
wrong and the build still succeeds and still diffs clean BY NID, while
consumers ask the loader for a library the module does not have.

THE ID ARITHMETIC, verified against the MSBuild artefacts:

  module ids   0 = this module, 1..n = the imported modules in IMPORT order
  library ids  0..n-1 = the imported libraries, n is SKIPPED,
               n+1.. = the exported libraries in .pemd order

The skipped id is not a mistake. libSceAppContent.prx built by the Prospero
toolchain imports three libraries (0,1,2) and puts its first export library at
4, and ampr_emu's module imports two (0,1) and exports at 3 -- in both cases
one past the end. Numbering the exports from n instead produces a module that
links, passes a NID diff, and asks the loader for the wrong library id.
"""

from __future__ import annotations

import base64
import hashlib
import re
import struct
from pathlib import Path

NID_SALT = bytes.fromhex("518D64A635DED8C1E6B039B1C3E55230")

# The order is the ABI. These become module ids 1,2,3 and library ids 0,1,2,
# and that is the order the Prospero-built modules use -- all three of them.
IMPORT_MODULES = ("libSceIpmi", "libkernel", "libSceLibcInternal")

SCE_NEEDED_MODULE = 0x61000045
SCE_IMPORT_LIB = 0x61000049
SCE_IMPORT_LIB_ATTR = 0x61000019
SCE_MODULE_INFO = 0x61000043
SCE_MODULE_FILENAME = 0x61000041
SCE_EXPORT_LIB = 0x61000047
SCE_EXPORT_LIB_ATTR = 0x61000017
SCE_FINGERPRINT = 0x61000011
SCE_SYMTABSZ = 0x6100003F
SCE_HASHSZ = 0x6100003D

MODULE_VERSION = 0x0101
LIBRARY_VERSION = 0x0001
IMPORT_LIB_ATTR = 9
EXPORT_LIB_ATTR = 1

# A .pemd may name an export by its NID instead of by a C name, for exports
# whose real name is not known. Those are used verbatim -- hashing a NID would
# produce the NID of the string, not the export.
_RAW_NID_RE = re.compile(r"^[A-Za-z0-9+-]{11}$")
_BASE64_DIGITS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
)


def name_to_nid(name: str) -> str:
    """The SCE export hash: SHA-1 over the name plus the salt, first 8 bytes
    big-endian, base64 with '+' and '-' as the last two digits."""
    digest = hashlib.sha1(name.encode("utf-8") + NID_SALT).digest()
    value = struct.unpack("<Q", digest[:8])[0]
    return (
        base64.b64encode(value.to_bytes(8, "big"), altchars=b"+-")
        .rstrip(b"=")
        .decode("ascii")
    )


def is_raw_nid(name: str) -> bool:
    return bool(_RAW_NID_RE.match(name)) and not name.startswith("sce")


def export_nid(name: str) -> str:
    return name if is_raw_nid(name) else name_to_nid(name)


def encode_id(value: int) -> str:
    """Encode a library or module id the way the SCE symbol suffix does."""
    if value < 0:
        raise ValueError(f"negative id {value}")
    if value < 64:
        return _BASE64_DIGITS[value]
    if value < 64 * 64:
        return _BASE64_DIGITS[value // 64] + _BASE64_DIGITS[value % 64]
    raise ValueError(f"id {value} is out of range for a two-digit suffix")


def suffixed(nid: str, library_id: int, module_id: int) -> str:
    return f"{nid}#{encode_id(library_id)}#{encode_id(module_id)}"


class Library:
    def __init__(self, name: str, version: int, functions: list[str]):
        self.name = name
        self.version = version
        self.functions = functions
        self.library_id = -1


class ModuleMeta:
    """Everything the link needs, derived from one .pemd."""

    def __init__(self, module: str, target: str, libraries: list[Library]):
        self.module = module
        self.target = target
        self.soname = f"{target}.prx"
        self.libraries = libraries
        for index, library in enumerate(libraries):
            library.library_id = self.first_export_library_id + index

    @property
    def first_export_library_id(self) -> int:
        return len(IMPORT_MODULES) + 1

    def import_library_id(self, module_name: str) -> int:
        return IMPORT_MODULES.index(module_name)

    def import_module_id(self, module_name: str) -> int:
        return IMPORT_MODULES.index(module_name) + 1

    def import_suffix(self, module_name: str) -> str:
        return (
            f"#{encode_id(self.import_library_id(module_name))}"
            f"#{encode_id(self.import_module_id(module_name))}"
        )

    def exports(self) -> list[tuple[str, str, Library]]:
        """(pemd name, suffixed symbol, library) for every exported function,
        in .pemd order. A C name listed under two libraries appears twice with
        two different symbols -- that is an alias, not a duplicate."""
        out = []
        for library in self.libraries:
            for name in library.functions:
                symbol = suffixed(export_nid(name), library.library_id, 0)
                out.append((name, symbol, library))
        return out

    def dynstr_names(self) -> list[str]:
        """Every string the SCE dynamic entries point at, deduplicated but
        order-stable. Each one needs a symbol in the link to reach .dynstr."""
        names = [*IMPORT_MODULES, self.module, self.soname]
        names += [library.name for library in self.libraries]
        seen, out = set(), []
        for name in names:
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def dynamic_entries(self) -> list[tuple[int, int, str | None]]:
        """(tag, value-without-name-offset, name) for the SCE half of
        .dynamic. lld will not emit these, so they are injected into the
        linker script as raw QUADs and their name offsets patched afterwards."""
        entries: list[tuple[int, int, str | None]] = []
        for name in IMPORT_MODULES:
            module_id = self.import_module_id(name)
            library_id = self.import_library_id(name)
            entries.append(
                (SCE_NEEDED_MODULE, (module_id << 48) | (MODULE_VERSION << 32), name)
            )
            entries.append(
                (SCE_IMPORT_LIB, (library_id << 48) | (LIBRARY_VERSION << 32), name)
            )
            entries.append(
                (SCE_IMPORT_LIB_ATTR, (library_id << 48) | IMPORT_LIB_ATTR, None)
            )
        entries.append(
            (SCE_MODULE_INFO, (MODULE_VERSION << 32), self.module)
        )
        entries.append((SCE_FINGERPRINT, 0, None))
        entries.append((SCE_MODULE_FILENAME, 0, self.soname))
        for library in self.libraries:
            entries.append(
                (
                    SCE_EXPORT_LIB,
                    (library.library_id << 48) | (library.version << 32),
                    library.name,
                )
            )
            entries.append(
                (
                    SCE_EXPORT_LIB_ATTR,
                    (library.library_id << 48) | EXPORT_LIB_ATTR,
                    None,
                )
            )
        return entries


_MODULE_RE = re.compile(r"^Module:\s*(\S+)", re.M)
_LIBRARY_RE = re.compile(r"^Library:\s*(\S+)\s*\{(.*?)^\}", re.M | re.S)
_VERSION_RE = re.compile(r"^\s*version:\s*(\d+)", re.M)
_FUNCTION_RE = re.compile(r"^\s*function:\s*(\S+)", re.M)


def parse_pemd(path: Path, target: str) -> ModuleMeta:
    text = path.read_text(encoding="utf-8")
    module_match = _MODULE_RE.search(text)
    if not module_match:
        raise ValueError(f"{path}: no 'Module:' line")
    libraries = []
    for name, body in _LIBRARY_RE.findall(text):
        version_match = _VERSION_RE.search(body)
        functions = _FUNCTION_RE.findall(body)
        if not functions:
            raise ValueError(f"{path}: library {name} exports nothing")
        libraries.append(
            Library(name, int(version_match.group(1)) if version_match else 1, functions)
        )
    if not libraries:
        raise ValueError(f"{path}: no 'Library:' block")
    return ModuleMeta(module_match.group(1), target, libraries)
