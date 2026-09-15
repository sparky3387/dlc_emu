/* Repository PRX CRT version prologue, built by ps5-payload-sdk. */
.section .sceversion,"",@progbits
.byte 0x00,0x00,0x16,0x00,0x08,0x63,0x72,0x74,0x69,0x3a,0x02,0x00,0x00
.byte 0x09,0x00,0x00,0x00,0x01,0x02,0x00,0x00,0x09,0x00,0x00,0x00,0x01

/* The CRT calls module_start/module_stop only if they exist, and a module that
   defines neither must still not leave a plain name in .dynsym -- the loader
   resolves by NID and has none for it. Clang drops visibility on an undefined
   weak C declaration, so mark them here, where the assembler keeps it. */
.weak module_start
.hidden module_start
.weak module_stop
.hidden module_stop

.section .note.GNU-stack,"",@progbits
