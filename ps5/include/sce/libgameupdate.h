#ifndef DLC_EMU_PAYLOAD_SDK_LIBGAMEUPDATE_H
#define DLC_EMU_PAYLOAD_SDK_LIBGAMEUPDATE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "libgameupdate_error.h"
#include "np/np_common.h"

#define SCE_GAME_UPDATE_CONTENT_VERSION_SIZE (11)

typedef struct SceGameUpdateCheckParam {
    size_t   size;
    uint32_t option;
    uint32_t reserved[9];
} SceGameUpdateCheckParam;

/* The explicit padding members carry the layout the caller expects; do not
 * let the compiler infer them, the trailing reserved[] would move. */
typedef struct SceGameUpdateCheckResult {
    size_t   size;
    bool     found;
    bool     addcontFound;
    char     padding[2];
    char     contentVersion[SCE_GAME_UPDATE_CONTENT_VERSION_SIZE];
    char     padding2[1];
    uint32_t reserved[6];
} SceGameUpdateCheckResult;

typedef struct SceGameUpdateAddcontVersionInfo {
    size_t   size;
    bool     found;
    char     contentVersion[SCE_GAME_UPDATE_CONTENT_VERSION_SIZE];
    uint32_t reserved[6];
} SceGameUpdateAddcontVersionInfo;

#endif
