# PRX linker script

`prx.script` lays out the fourteen segments a PS5 module needs. The loader
finds each segment by type rather than by position, so the order here differs
from the Prospero-built module's while the set is the same.

Two things the script cannot do on its own:

- LLD does not know Sony's `PT_SCE_*` program-header types by name, so
  `tools/prepare_prx_link_script.py` substitutes the numbers before the link.
- LLD sizes `.dynamic` at layout time and leaves no room to append, so the SCE
  dynamic entries are injected as raw `QUAD` pairs ahead of `*(.dynamic)`.
  Their name offsets are meaningless until `.dynstr` exists;
  `tools/stamp_payload_prx.py` patches them afterwards.

`(INFO)` gets `p_vaddr` to 0 on the unloadable segments, which is necessary but
not sufficient: LLD still derives `p_memsz` from `p_filesz`, and an unloadable
segment that claims address space makes the loader refuse the whole module.
The stamper zeroes those. `PT_SCE_LIBVERSION` keeps its size deliberately --
the Prospero-built module does too.
