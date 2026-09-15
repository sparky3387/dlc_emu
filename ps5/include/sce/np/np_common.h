#ifndef DLC_EMU_PAYLOAD_SDK_NP_COMMON_H
#define DLC_EMU_PAYLOAD_SDK_NP_COMMON_H

#include <stdint.h>

#define SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE (17)
#define SCE_NP_SERVICE_ENTITLEMENT_LABEL_SIZE (7)

typedef uint32_t SceNpServiceLabel;

/* Both labels are padded out to 20 bytes. The padding is part of the ABI: a
 * caller passes these by value in arrays, so a short struct silently
 * misaligns every element after the first. */
typedef struct SceNpUnifiedEntitlementLabel {
    char data[SCE_NP_UNIFIED_ENTITLEMENT_LABEL_SIZE];
    char padding[3];
} SceNpUnifiedEntitlementLabel;

typedef struct SceNpServiceEntitlementLabel {
    char data[SCE_NP_SERVICE_ENTITLEMENT_LABEL_SIZE];
    char padding[13];
} SceNpServiceEntitlementLabel;

#endif
