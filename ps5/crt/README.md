# Repository PRX CRT

These sources implement the repository PRX startup/shutdown contract without
requiring prebuilt objects. `Makefile` compiles all four inputs with the
payload-SDK compiler and keeps their original link order:

- `crti.S`: `.sceversion` prologue record.
- `crtbeginS.c`: `_fini`, module parameters, DSO/libc anchors, and ctor/dtor
  start sentinels.
- `crtendS.c`: `_init` plus preinit/constructor dispatch and end sentinels.
- `crtn.S`: `.sceversion` epilogue record.

The C implementations preserve weak `module_start`, `module_stop`, and
`__cxa_finalize` behavior. `__cxa_finalize` is deliberately unresolved here
and becomes a `libSceLibcInternal.prx` NID import.

`crti.S` also marks `module_start` and `module_stop` hidden. Clang drops
visibility from an undefined weak C declaration, and a module that defines
neither -- `libSceGameUpdate` -- would otherwise leave a plain name in
`.dynsym` that the loader has no NID for.
