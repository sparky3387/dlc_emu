#ifndef DLC_EMU_PAYLOAD_SDK_NP_ENTITLEMENT_ACCESS_H
#define DLC_EMU_PAYLOAD_SDK_NP_ENTITLEMENT_ACCESS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "_rtc.h"
#include "np/np_common.h"
#include "user_service.h"

#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NOT_INITIALIZED   -2122514431 /* 0x8158A001 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_PARAMETER         -2122514430 /* 0x8158A002 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_BUSY              -2122514429 /* 0x8158A003 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NOT_FOUND         -2122514427 /* 0x8158A005 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NO_ENTITLEMENT    -2122514425 /* 0x8158A007 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_INTERNAL          -2122514422 /* 0x8158A00A */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NOT_SUPPORTED     -2122514423 /* 0x8158A009 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_OUT_OF_MEMORY     -2122514416 /* 0x8158A010 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_USER_NOT_FOUND    -2122514409 /* 0x8158A017 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_ABORTED           -2122514410 /* 0x8158A016 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_REQUEST_NOT_FOUND -2122514411 /* 0x8158A015 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_SIGNED_OUT        -2122514412 /* 0x8158A014 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_NETWORK           -2122514413 /* 0x8158A013 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_TIMEOUT           -2122514408 /* 0x8158A018 */
#define SCE_NP_ENTITLEMENT_ACCESS_ERROR_TITLE_TOKEN       -2122514407 /* 0x8158A019 */

#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_KEY_SIZE (16)
#define SCE_NP_ENTITLEMENT_ACCESS_TRANSACTION_ID_MAX_SIZE (65)
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_INFO_LIST_MAX_SIZE (100)
#define SCE_NP_ENTITLEMENT_ACCESS_ADDCONT_ENTITLEMENT_INFO_LIST_MAX_SIZE (2500)

#define SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_TRIAL (1)
#define SCE_NP_ENTITLEMENT_ACCESS_SKU_FLAG_FULL  (3)

/* SCE_NP_ENTITLEMENT_ACCESS_GAME_TRIALS_FLAG_OFF/_ON are NOT declared here,
 * because 4.00 does not declare them either. dlc_content.h keys its own
 * SceNpEntitlementAccessGameTrialsFlag typedef off _OFF being undefined, so
 * defining it here leaves that type missing on this route alone. */

#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_NONE    (0)
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_SERVICE (1)
#define SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_TYPE_UNIFIED (2)

#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_NONE   (0)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSGD   (1)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAC   (2)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSAL   (3)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSCONS (4)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSVC   (5)
#define SCE_NP_ENTITLEMENT_ACCESS_PACKAGE_TYPE_PSSUBS (6)

#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_NO_EXTRA_DATA       (0)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_NO_IN_QUEUE         (1)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_DOWNLOADING         (2)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_DOWNLOAD_SUSPENDED  (3)
#define SCE_NP_ENTITLEMENT_ACCESS_DOWNLOAD_STATUS_INSTALLED           (4)

#define SCE_NP_ENTITLEMENT_ACCESS_SORT_TYPE_NONE        (0)
#define SCE_NP_ENTITLEMENT_ACCESS_SORT_TYPE_ACTIVE_DATE (1)

#define SCE_NP_ENTITLEMENT_ACCESS_DIRECTION_TYPE_NONE (0)
#define SCE_NP_ENTITLEMENT_ACCESS_DIRECTION_TYPE_ASC  (1)
#define SCE_NP_ENTITLEMENT_ACCESS_DIRECTION_TYPE_DESC (2)

#define SCE_NP_ENTITLEMENT_ACCESS_POLL_RET_FINISHED       (0)
#define SCE_NP_ENTITLEMENT_ACCESS_POLL_ASYNC_RET_RUNNING  (1)

#define SCE_NP_ENTITLEMENT_ACCESS_INVALID_OFFSET (-1)
#define SCE_NP_ENTITLEMENT_ACCESS_INVALID_DATE (0xffffffffffffffffUL)

typedef uint32_t SceNpEntitlementAccessSkuFlag;
typedef uint32_t SceNpEntitlementAccessEntitlementType;
typedef uint32_t SceNpEntitlementAccessPackageType;
typedef uint32_t SceNpEntitlementAccessDownloadStatus;
typedef uint32_t SceNpEntitlementAccessSortType;
typedef uint32_t SceNpEntitlementAccessDirectionType;

typedef struct SceNpEntitlementAccessInitParam {
    char reserved[32];
} SceNpEntitlementAccessInitParam;

typedef struct SceNpEntitlementAccessBootParam {
    char reserved[32];
} SceNpEntitlementAccessBootParam;

typedef struct SceNpEntitlementAccessEntitlementKey {
    char data[SCE_NP_ENTITLEMENT_ACCESS_ENTITLEMENT_KEY_SIZE];
} SceNpEntitlementAccessEntitlementKey;

typedef struct SceNpEntitlementAccessTransactionId {
    char transactionId[SCE_NP_ENTITLEMENT_ACCESS_TRANSACTION_ID_MAX_SIZE];
    char padding[7];
} SceNpEntitlementAccessTransactionId;

typedef struct SceNpEntitlementAccessAddcontEntitlementInfo {
    SceNpUnifiedEntitlementLabel         entitlementLabel;
    SceNpEntitlementAccessPackageType    packageType;
    SceNpEntitlementAccessDownloadStatus downloadStatus;
} SceNpEntitlementAccessAddcontEntitlementInfo;

typedef struct SceNpEntitlementAccessUnifiedEntitlementInfo {
    SceNpUnifiedEntitlementLabel          entitlementLabel;
    SceRtcTick                            activeDate;
    SceRtcTick                            inactiveDate;
    SceNpEntitlementAccessEntitlementType entitlementType;
    int32_t                               useCount;
    int32_t                               useLimit;
    SceNpEntitlementAccessPackageType     packageType;
    bool                                  activeFlag;
    int8_t                                reserved[3];
} SceNpEntitlementAccessUnifiedEntitlementInfo;

typedef struct SceNpEntitlementAccessServiceEntitlementInfo {
    SceNpServiceEntitlementLabel          entitlementLabel;
    SceRtcTick                            activeDate;
    SceRtcTick                            inactiveDate;
    SceNpEntitlementAccessEntitlementType entitlementType;
    int32_t                               useCount;
    int32_t                               useLimit;
    uint32_t                              reserved1;
    bool                                  activeFlag;
    bool                                  isConsumable;
    int8_t                                reserved2[2];
} SceNpEntitlementAccessServiceEntitlementInfo;

typedef struct SceNpEntitlementAccessRequestEntitlementInfoListParam {
    size_t                                size;
    SceNpEntitlementAccessEntitlementType entitlementType;
    int32_t                               offset;
    int32_t                               limit;
    SceNpEntitlementAccessSortType        sort;
    SceNpEntitlementAccessDirectionType   direction;
    SceNpEntitlementAccessPackageType     packageType;
} SceNpEntitlementAccessRequestEntitlementInfoListParam;

#endif
