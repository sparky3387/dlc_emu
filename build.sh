#!/bin/sh
# Build both module variants with ps5-payload-sdk, the way the Windows solution
# builds ReleaseHooks|Prospero twice with and without SCE_DLC_EMU_LOG.
#
#   ./build.sh                 both variants into out/payload-sdk/{nolog,log}
#   ./build.sh nolog           one variant
#   PS5_PAYLOAD_SDK=... ./build.sh
#   JOBS=8 ./build.sh
#
# Each variant gets its own object tree: the two differ only by a -D, so
# sharing objects would silently ship whichever was compiled last.

set -eu

PS5_PAYLOAD_SDK="${PS5_PAYLOAD_SDK:-/opt/ps5-payload-sdk}"
MAKE="${MAKE:-make}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"
OUT_ROOT="${OUT_ROOT:-out/payload-sdk}"

cd "$(dirname "$0")"

if [ ! -f "$PS5_PAYLOAD_SDK/toolchain/prospero.mk" ]; then
    echo "build.sh: no ps5-payload-sdk at $PS5_PAYLOAD_SDK" >&2
    echo "  set PS5_PAYLOAD_SDK to the install root" >&2
    exit 1
fi

variant_defs() {
    case "$1" in
        nolog) echo "" ;;
        log) echo "-DSCE_DLC_EMU_LOG=1" ;;
        *) echo "build.sh: unknown variant '$1' (want nolog or log)" >&2; exit 1 ;;
    esac
}

build_variant() {
    variant="$1"
    defs="$(variant_defs "$variant")"
    echo "=== $variant ==="
    PS5_PAYLOAD_SDK="$PS5_PAYLOAD_SDK" "$MAKE" -j"$JOBS" verify \
        OUT="$OUT_ROOT/$variant" EXTRA_DEFS="$defs"
}

VARIANTS="${*:-nolog log}"

for variant in $VARIANTS; do
    build_variant "$variant"
done

echo
echo "built:"
for variant in $VARIANTS; do
    for module in libSceAppContent libSceGameUpdate libSceNpEntitlementAccess; do
        echo "  $OUT_ROOT/$variant/$module.sprx"
    done
done
