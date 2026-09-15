#!/usr/bin/env python3
"""Adapt the repository PRX linker script for upstream LLD, and inject the SCE
dynamic entries lld will not emit.

lld sizes .dynamic at layout time and leaves no room to append afterwards, so
the SCE half has to be present as raw QUAD pairs in the script itself. Their
name offsets are meaningless here -- tools/stamp_payload_prx.py patches them
once .dynstr exists.

The entries are generated from the module's own metadata, so a module that
exports seven libraries gets seven DT_SCE_EXPORT_LIB entries without anyone
editing a table by hand.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# LLD knows the ELF-generic PHDR types by name but not Sony's.
PHDR_TYPES = {
    "PT_SCE_MODULEPARAM": "0x61000002",
    "PT_SCE_COMMENT": "0x6fffff00",
    "PT_SCE_LIBVERSION": "0x6fffff01",
}

DYNAMIC_INPUT = "        *(.dynamic)"


def render_dynamic(meta: dict) -> str:
    lines = [
        "        /* SCE entries supplied at link time; ordinary ELF entries follow."
    ]
    lines.append(
        f"           Generated for {meta['module']} by tools/prepare_prx_link_script.py."
    )
    lines.append("           The low 32 bits are .dynstr offsets, patched post-link. */")
    for entry in meta["dynamic"]:
        lines.append(f"        QUAD ({entry['tag']:#x}); QUAD ({entry['value']:#018x})")
    lines.append("        QUAD (0x6100003f); QUAD (SIZEOF (.dynsym))")
    lines.append("        QUAD (0x6100003d); QUAD (SIZEOF (.hash))")
    lines.append("        *(.dynamic)")
    return "\n".join(lines)


def adapt(text: str, meta: dict) -> str:
    for name, value in PHDR_TYPES.items():
        count = text.count(name)
        if count != 1:
            raise ValueError(
                f"expected one {name} in the repository prx.script, found {count}"
            )
        text = text.replace(name, value)

    if text.count(DYNAMIC_INPUT) != 1:
        raise ValueError("repository prx.script .dynamic rule changed")
    return text.replace(DYNAMIC_INPUT, render_dynamic(meta))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--meta-json", type=Path, required=True)
    args = parser.parse_args()

    meta = json.loads(args.meta_json.read_text())
    output = adapt(args.input.read_text(encoding="utf-8"), meta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print(
        f"prepared PRX script for {meta['target']}: "
        f"{len(meta['dynamic'])} SCE dynamic entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
