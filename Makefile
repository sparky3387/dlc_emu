# Self-contained Linux PRX build for the dlc_emu replacement modules.
#
#   make                 build all three modules into out/payload-sdk
#   make verify          build, then check the result against the .pemd files
#   make MODULES=...     build a subset
#   make clean
#   ./build.sh           build the nolog and log variants, the way
#                        build_both.cmd does on the Windows route
#
# The Windows ReleaseHooks|Prospero solution is unaffected and remains the
# reference; this route produces the same three modules with ps5-payload-sdk
# and upstream LLD, neither of which can read a .pemd or emit SCE dynamic
# entries. tools/dlc_prx_meta.py closes both gaps.

PS5_PAYLOAD_SDK ?= /opt/ps5-payload-sdk
PYTHON ?= python3
BUILD_MAKEFILE := $(lastword $(MAKEFILE_LIST))

include $(PS5_PAYLOAD_SDK)/toolchain/prospero.mk

LLVM_BINDIR := $(shell $(PS5_PAYLOAD_SDK)/bin/prospero-llvm-config --bindir)
PRX_LD := $(LLVM_BINDIR)/ld.lld

# Overridable so build.sh can give each variant its own tree. Two builds that
# differ only by a -D must not be able to see each other's objects.
OUT ?= out/payload-sdk
OBJ := $(OUT)/obj
CRT_DIR := $(OBJ)/sce-crt

MODULES ?= libSceAppContent libSceGameUpdate libSceNpEntitlementAccess

# Must stay in step with IMPORT_MODULES in tools/dlc_prx_meta.py: the order is
# the module and library id order, not just a list of names.
PRX_IMPORT_MODULES := libSceIpmi libkernel libSceLibcInternal

# Every module is the shared emulation plus its own export layer, matching the
# three ClCompile lists in msbuild/*/*.vcxproj.
COMMON_SOURCES := src/dlc_modules/dlc_content.cpp src/dlc_modules/dlc_log.cpp
libSceAppContent_EXPORTS := src/dlc_modules/sceappcontent_exports.cpp
libSceGameUpdate_EXPORTS := src/dlc_modules/scegameupdate_exports.cpp
libSceNpEntitlementAccess_EXPORTS := src/dlc_modules/scenpentitlementaccess_exports.cpp

libSceAppContent_DEFS := -DLIBSCEAPPCONTENT_IMPL=1
libSceGameUpdate_DEFS := -DLIBSCEGAMEUPDATE_IMPL=1
libSceNpEntitlementAccess_DEFS := -DLIBSCENPENTITLEMENTACCESS_IMPL=1

# The fself version the Windows route stamps. Raising it would refuse to load
# on the firmware these modules exist for.
FSELF_VERSION := 0x02000001

# ps5/include/sce with -idirafter, NOT -I: the payload toolchain's own libc and
# system headers stay primary and the shim fills only the Prospero declarations
# it does not provide. src/kernel.h and src/_fs.h rely on that order for their
# #include_next.
COMMON_DEFS := -Drestrict=__restrict -DNDEBUG
COMMON_FLAGS := \
  -fPIC -fplt -O3 -fno-strict-aliasing \
  -ffunction-sections -fdata-sections -fvisibility=hidden \
  -Isrc -idirafter ps5/include/sce $(COMMON_DEFS)

# EXTRA_DEFS is the ONE difference between the nolog and log variants;
# build.sh passes -DSCE_DLC_EMU_LOG=1 for the second, exactly as
# build_both.cmd sets DlcExtraPreprocessorDefinitions.
EXTRA_DEFS ?=

CXXFLAGS += -std=c++17 -fno-exceptions -fno-rtti -fvisibility-inlines-hidden \
            $(COMMON_FLAGS) $(EXTRA_DEFS)

CRT_CFLAGS := -std=c11 -O2 -fPIC -fplt -ffreestanding -fno-stack-protector \
              -fno-asynchronous-unwind-tables -fno-unwind-tables \
              -fvisibility=hidden

CRT_OBJECTS := $(CRT_DIR)/crti.o $(CRT_DIR)/crtbeginS.o \
               $(CRT_DIR)/crtendS.o $(CRT_DIR)/crtn.o

PRX_SCRIPT_SOURCE := ps5/prx/prx.script

PRXS := $(foreach m,$(MODULES),$(OUT)/$(m).prx)
SPRXS := $(foreach m,$(MODULES),$(OUT)/$(m).sprx)

.DELETE_ON_ERROR:
.SECONDARY:
.DEFAULT_GOAL := all
.PHONY: all clean verify print-vars

all: $(SPRXS)

# ---------------------------------------------------------------------------
# Per-module rules. Each module compiles its own objects, because the shared
# sources are built with a different -DLIBSCE*_IMPL for each one.
# ---------------------------------------------------------------------------
define MODULE_rules

$(1)_OBJ := $$(OBJ)/$(1)
$(1)_GEN := $$(OBJ)/$(1)/generated
$(1)_SRCS := $$(COMMON_SOURCES) $$($(1)_EXPORTS)
$(1)_OBJECTS := $$(patsubst src/dlc_modules/%.cpp,$$(OBJ)/$(1)/%.o,$$($(1)_SRCS))
$(1)_RENAMED := $$(patsubst $$(OBJ)/$(1)/%.o,$$(OBJ)/$(1)/nids/%.o,$$($(1)_OBJECTS))
$(1)_CRT := $$(patsubst $$(CRT_DIR)/%.o,$$(OBJ)/$(1)/nids/sce-crt/%.o,$$(CRT_OBJECTS))

$$(OBJ)/$(1)/%.o: src/dlc_modules/%.cpp $$(BUILD_MAKEFILE)
	@mkdir -p $$(dir $$@)
	$$(CXX) $$(CXXFLAGS) $$($(1)_DEFS) -MD -MP -c $$< -o $$@

# ONE relocatable object first, so `nm -u` reports what is genuinely
# unresolved. Run per-object it also lists every cross-object reference, and
# those would be classified as firmware imports.
$$(OBJ)/$(1)/link/$(1).combined.o: $$($(1)_OBJECTS) $$(CRT_OBJECTS)
	@mkdir -p $$(dir $$@)
	$$(PRX_LD) -m elf_x86_64 -r -o $$@ $$($(1)_OBJECTS) $$(CRT_OBJECTS)

$$($(1)_GEN)/$(1).undefined.txt: $$(OBJ)/$(1)/link/$(1).combined.o
	@mkdir -p $$(dir $$@)
	$$(NM) -u -j $$< | LC_ALL=C sort -u > $$@

$$($(1)_GEN)/$(1).stamp: \
    $$($(1)_GEN)/$(1).undefined.txt msbuild/pemd/$(1).pemd \
    tools/generate_payload_exports.py tools/dlc_prx_meta.py $$(BUILD_MAKEFILE)
	@mkdir -p $$($(1)_GEN)
	$$(PYTHON) tools/generate_payload_exports.py \
	  --pemd msbuild/pemd/$(1).pemd --target $(1) \
	  --undefined $$($(1)_GEN)/$(1).undefined.txt \
	  --response $$($(1)_GEN)/$(1).exports.rsp \
	  --version-script $$($(1)_GEN)/$(1).version.script \
	  --rename-map $$($(1)_GEN)/$(1).rename.txt \
	  --alias-list $$($(1)_GEN)/$(1).aliases.txt \
	  --metadata-asm $$($(1)_GEN)/$(1).metadata.S \
	  --stub-dir $$($(1)_GEN) \
	  --meta-json $$($(1)_GEN)/$(1).meta.json
	@touch $$@

$(1)_GENERATED_INPUTS := \
  $$($(1)_GEN)/$(1).rename.txt $$($(1)_GEN)/$(1).exports.rsp \
  $$($(1)_GEN)/$(1).version.script $$($(1)_GEN)/$(1).aliases.txt \
  $$($(1)_GEN)/$(1).metadata.S $$($(1)_GEN)/$(1).meta.json \
  $$(foreach mod,$$(PRX_IMPORT_MODULES),$$($(1)_GEN)/$$(mod).imports.S) \
  $$(foreach mod,$$(PRX_IMPORT_MODULES),$$($(1)_GEN)/$$(mod).imports.txt)

$$($(1)_GENERATED_INPUTS): $$($(1)_GEN)/$(1).stamp
	@test -f $$@ || { echo "missing generated PRX input: $$@" >&2; exit 1; }

$$(OBJ)/$(1)/nids/%.o: $$(OBJ)/$(1)/%.o $$($(1)_GEN)/$(1).rename.txt
	@mkdir -p $$(dir $$@)
	cp $$< $$@
	$$(OBJCOPY) @$$($(1)_GEN)/$(1).rename.txt $$@

$$(OBJ)/$(1)/nids/sce-crt/%.o: $$(CRT_DIR)/%.o $$($(1)_GEN)/$(1).rename.txt
	@mkdir -p $$(dir $$@)
	cp $$< $$@
	$$(OBJCOPY) @$$($(1)_GEN)/$(1).rename.txt $$@

# Exports that two libraries share become a second symbol on the definition
# that is already there. This has to happen after the rename, and before the
# link asks the version script to export both names.
$$(OBJ)/$(1)/nids/$(1).aliases.stamp: \
    $$($(1)_RENAMED) $$($(1)_GEN)/$(1).aliases.txt tools/add_alias_symbols.py
	$$(PYTHON) tools/add_alias_symbols.py --objcopy $$(OBJCOPY) \
	  --aliases $$($(1)_GEN)/$(1).aliases.txt $$($(1)_RENAMED)
	@touch $$@

# One shared object per imported module. Their sonames become the module's
# DT_SCE_NEEDED_MODULE entries and their symbols carry the importing NIDs.
$$($(1)_GEN)/%.prx.so: $$($(1)_GEN)/%.imports.S $$(BUILD_MAKEFILE)
	$$(CC) -shared -nostdlib -nodefaultlibs \
	  -Wl,--hash-style=sysv -Wl,-soname,$$*.prx -o $$@ $$<

$$($(1)_GEN)/$(1).metadata.o: $$($(1)_GEN)/$(1).metadata.S
	$$(CC) -c $$< -o $$@

$$($(1)_GEN)/prx.script: \
    $$(PRX_SCRIPT_SOURCE) $$($(1)_GEN)/$(1).meta.json \
    tools/prepare_prx_link_script.py $$(BUILD_MAKEFILE)
	@mkdir -p $$(dir $$@)
	$$(PYTHON) tools/prepare_prx_link_script.py $$(PRX_SCRIPT_SOURCE) $$@ \
	  --meta-json $$($(1)_GEN)/$(1).meta.json

$(1)_STUB_SOS := $$(foreach mod,$$(PRX_IMPORT_MODULES),$$($(1)_GEN)/$$(mod).prx.so)

# --no-as-needed around the stubs, or a module that imports nothing from one of
# them drops the DT_SCE_NEEDED_MODULE entry and the id arithmetic shifts.
$$(OBJ)/$(1)/link/$(1).prx: \
    $$($(1)_RENAMED) $$($(1)_CRT) $$($(1)_GEN)/$(1).metadata.o \
    $$(OBJ)/$(1)/nids/$(1).aliases.stamp $$($(1)_STUB_SOS) \
    $$($(1)_GEN)/prx.script $$($(1)_GEN)/$(1).exports.rsp \
    $$($(1)_GEN)/$(1).version.script tools/stamp_payload_prx.py $$(BUILD_MAKEFILE)
	@mkdir -p $$(dir $$@)
	$$(PRX_LD) -m elf_x86_64 --shared --eh-frame-hdr -mllvm -emulated-tls \
	  -T $$($(1)_GEN)/prx.script --hash-style=sysv --build-id=sha1 -z relro \
	  -z max-page-size=0x4000 -z common-page-size=0x4000 \
	  --version-script=$$($(1)_GEN)/$(1).version.script -o $$@ \
	  $$(OBJ)/$(1)/nids/sce-crt/crti.o $$(OBJ)/$(1)/nids/sce-crt/crtbeginS.o \
	  $$($(1)_RENAMED) $$($(1)_GEN)/$(1).metadata.o \
	  $$(OBJ)/$(1)/nids/sce-crt/crtendS.o $$(OBJ)/$(1)/nids/sce-crt/crtn.o \
	  --no-as-needed $$($(1)_STUB_SOS) --as-needed \
	  @$$($(1)_GEN)/$(1).exports.rsp
	$$(PYTHON) tools/stamp_payload_prx.py $$@ \
	  --meta-json $$($(1)_GEN)/$(1).meta.json

# lld hashes the literal short name in .dynstr; the loader hashes the EXPANDED
# name. Every lld-linked PRX has its exports in the wrong .hash buckets until
# this puts them back.
$$(OUT)/$(1).prx: $$(OBJ)/$(1)/link/$(1).prx $$($(1)_GEN)/$(1).meta.json tools/prx_hash_fix.py
	@mkdir -p $$(dir $$@)
	$$(PYTHON) tools/prx_hash_fix.py $$< $$@ \
	  --meta-json $$($(1)_GEN)/$(1).meta.json

$$(OUT)/$(1).sprx: $$(OUT)/$(1).prx tools/make_fself.py
	$$(PYTHON) tools/make_fself.py $$< $$@ --ptype fake \
	  --app-version $$(FSELF_VERSION) --fw-version $$(FSELF_VERSION)

-include $$($(1)_OBJECTS:.o=.d)

endef

$(foreach m,$(MODULES),$(eval $(call MODULE_rules,$(m))))

$(CRT_DIR)/%.o: ps5/crt/%.c $(BUILD_MAKEFILE)
	@mkdir -p $(dir $@)
	$(CC) $(CRT_CFLAGS) -c $< -o $@

$(CRT_DIR)/%.o: ps5/crt/%.S $(BUILD_MAKEFILE)
	@mkdir -p $(dir $@)
	$(CC) -c $< -o $@

verify: all
	$(PYTHON) tools/verify_payload_prx.py --out $(OUT) --modules $(MODULES)

clean:
	rm -rf $(OUT)

print-vars:
	@echo "PS5_PAYLOAD_SDK=$(PS5_PAYLOAD_SDK)"
	@echo "OUT=$(OUT)"
	@echo "MODULES=$(MODULES)"
	@echo "EXTRA_DEFS=$(EXTRA_DEFS)"
