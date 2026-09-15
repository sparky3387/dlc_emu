#!/usr/bin/env python3
"""Generate the NID names and import providers for the payload-SDK PRX link.

The Prospero linker reads the .pemd and hashes export names into NIDs itself.
lld cannot, so the same job is done here, before the link: every export is
renamed to its suffixed NID with objcopy, and every import is satisfied by a
generated stub shared object whose symbols carry the importing NID names.

See tools/dlc_prx_meta.py for the id arithmetic this relies on.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dlc_prx_meta import IMPORT_MODULES, ModuleMeta, name_to_nid, parse_pemd

# Provided by the linker script (ps5/prx/prx.script), so they are undefined in
# the combined object and must never be mistaken for firmware imports.
SCRIPT_PROVIDED = {
    "__CTOR_LIST__",
    "__CTOR_END__",
    "__DTOR_LIST__",
    "__DTOR_END__",
    "__start__Zpreinit_array",
    "__stop__Zpreinit_array",
}

# The module entry points. libSceGameUpdate defines neither, and the CRT tests
# them for NULL -- they must stay unresolved rather than become an import of a
# firmware library that does not export them. ps5/crt declares them hidden so
# an absent one does not reach .dynsym either.
WEAK_OPTIONAL = {
    "module_start",
    "module_stop",
}

CRT_PROVIDED = {"__dso_handle"}

# EVERY firmware import, named. Classification is by explicit membership and
# not by a "everything else is libc" fallback, because the cost of guessing
# wrong is silent: an import filed under the wrong library still links, and
# only fails when the loader cannot find that NID in that library.
LIBC_IMPORTS = {
    "Need_sceLibcInternal",
    "__cxa_atexit",
    "__cxa_finalize",
    "__cxa_guard_acquire",
    "__cxa_guard_release",
    "abort",
    "calloc",
    "free",
    "isalnum",
    "isxdigit",
    "malloc",
    "memchr",
    "memcmp",
    "memcpy",
    "memmove",
    "memset",
    "realloc",
    "snprintf",
    "strcasecmp",
    "strchr",
    "strcmp",
    "strlcpy",
    "strlen",
    "strncmp",
    "strnlen",
    "strrchr",
    "strstr",
    "strtol",
    "strtoll",
    "strtoul",
    "strtoull",
    "tolower",
    "toupper",
    "vsnprintf",
}

KERNEL_IMPORTS = {
    "__error",
    "__stack_chk_fail",
    "__stack_chk_guard",
}

IPMI_PREFIX = "_ZN4IPMI"


def classify(name: str) -> str:
    """Return the importing module name for one undefined symbol."""
    if name.startswith(IPMI_PREFIX):
        return "libSceIpmi"
    if name in KERNEL_IMPORTS or name.startswith(("sceKernel", "scePthread")):
        return "libkernel"
    if name in LIBC_IMPORTS:
        return "libSceLibcInternal"
    raise ValueError(
        f"unclassified PRX import {name!r}. Add it to LIBC_IMPORTS or "
        f"KERNEL_IMPORTS in {Path(__file__).name} -- do not guess, check which "
        f"firmware library actually exports the NID."
    )


def read_undefined(path: Path) -> list[str]:
    names = {line.strip() for line in path.read_text().splitlines() if line.strip()}
    return sorted(names - SCRIPT_PROVIDED - WEAK_OPTIONAL - CRT_PROVIDED)


def render_rename_map(renames: list[tuple[str, str]]) -> str:
    return "".join(f'"--redefine-sym={old}={new}"\n' for old, new in renames)


def render_response(symbols: list[str]) -> str:
    return "".join(f'"--export-dynamic-symbol={s}"\n' for s in symbols)


def render_version_script(symbols: list[str]) -> str:
    body = "".join(f'    "{s}";\n' for s in symbols)
    return "{\n  global:\n" + body + "  local: *;\n};\n"


def render_alias_list(aliases: list[tuple[str, str]]) -> str:
    """A C name listed under two .pemd libraries is ONE function exported
    twice. objcopy can rename the definition only once, so every further
    library gets an alias symbol at the same address -- see
    tools/add_alias_symbols.py, which consumes this list."""
    return "".join(f"{alias}\t{primary}\n" for alias, primary in aliases)


def render_stub_assembly(module: str, symbols: list[str]) -> str:
    lines = [f"/* Auto-generated NID import provider for {module}. */", ".text"]
    for symbol in symbols:
        lines += [
            f'.globl "{symbol}"',
            f'.type "{symbol}", @function',
            f'"{symbol}":',
            "    ret",
            f'.size "{symbol}", .-"{symbol}"',
        ]
    lines.append('.section .note.GNU-stack,"",@progbits')
    return "\n".join(lines) + "\n"


def render_metadata_assembly(names: list[str]) -> str:
    """The SCE dynamic entries name modules and libraries by .dynstr offset,
    and lld only puts a string in .dynstr if some dynamic symbol has that
    name. These zero-byte objects exist to carry those names and nothing
    else; tools/stamp_payload_prx.py patches the offsets afterwards."""
    lines = ["/* Auto-generated link-only SCE dynamic string markers. */", ".data"]
    for name in names:
        lines += [
            f'.globl "{name}"',
            f'.protected "{name}"',
            f'.type "{name}", @object',
            f'"{name}":',
            "    .byte 0",
            f'.size "{name}", 1',
        ]
    lines.append('.section .note.GNU-stack,"",@progbits')
    return "\n".join(lines) + "\n"


def write_if_changed(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == data:
        return
    path.write_text(data, encoding="utf-8")


def build(meta: ModuleMeta, undefined: list[str]) -> dict:
    renames: list[tuple[str, str]] = []
    aliases: list[tuple[str, str]] = []
    export_symbols: list[str] = []
    primary: dict[str, str] = {}

    for name, symbol, _library in meta.exports():
        export_symbols.append(symbol)
        if name in primary:
            aliases.append((symbol, primary[name]))
        else:
            primary[name] = symbol
            renames.append((name, symbol))

    imports: dict[str, list[str]] = {module: [] for module in IMPORT_MODULES}
    for name in undefined:
        module = classify(name)
        imports[module].append(name)
        renames.append((name, f"{name_to_nid(name)}{meta.import_suffix(module)}"))

    metadata = meta.dynstr_names()
    return {
        "renames": renames,
        "aliases": aliases,
        "export_symbols": export_symbols,
        "imports": imports,
        "metadata": metadata,
        "linked_symbols": export_symbols + metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pemd", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--undefined", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--version-script", type=Path, required=True)
    parser.add_argument("--rename-map", type=Path, required=True)
    parser.add_argument("--alias-list", type=Path, required=True)
    parser.add_argument("--metadata-asm", type=Path, required=True)
    parser.add_argument("--stub-dir", type=Path, required=True)
    parser.add_argument("--meta-json", type=Path, required=True)
    args = parser.parse_args()

    meta = parse_pemd(args.pemd, args.target)
    plan = build(meta, read_undefined(args.undefined))

    write_if_changed(args.response, render_response(plan["linked_symbols"]))
    write_if_changed(args.version_script, render_version_script(plan["linked_symbols"]))
    write_if_changed(args.rename_map, render_rename_map(plan["renames"]))
    write_if_changed(args.alias_list, render_alias_list(plan["aliases"]))
    write_if_changed(args.metadata_asm, render_metadata_assembly(plan["metadata"]))

    counts = []
    for module, names in plan["imports"].items():
        suffix = meta.import_suffix(module)
        symbols = [f"{name_to_nid(name)}{suffix}" for name in names]
        write_if_changed(
            args.stub_dir / f"{module}.imports.S", render_stub_assembly(module, symbols)
        )
        write_if_changed(
            args.stub_dir / f"{module}.imports.txt", "\n".join(names) + "\n"
        )
        counts.append(f"{module}={len(names)}")

    write_if_changed(
        args.meta_json,
        json.dumps(
            {
                "module": meta.module,
                "target": meta.target,
                "soname": meta.soname,
                "import_modules": list(IMPORT_MODULES),
                "export_libraries": [
                    {"name": lib.name, "id": lib.library_id, "version": lib.version}
                    for lib in meta.libraries
                ],
                "dynamic": [
                    {"tag": tag, "value": value, "name": name}
                    for tag, value, name in meta.dynamic_entries()
                ],
                "dynstr_names": plan["metadata"],
            },
            indent=2,
        )
        + "\n",
    )

    print(
        f"{meta.target}: module={meta.module} "
        f"exports={len(plan['export_symbols'])} "
        f"(aliases={len(plan['aliases'])}) "
        f"libs={len(meta.libraries)}@{meta.libraries[0].library_id}.. "
        f"imports {' '.join(counts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
