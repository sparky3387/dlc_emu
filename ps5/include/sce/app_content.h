#ifndef DLC_EMU_PAYLOAD_SDK_APP_CONTENT_H
#define DLC_EMU_PAYLOAD_SDK_APP_CONTENT_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "np/np_common.h"
#include "sdk_version.h"

/* DELIBERATELY ABSENT, because the 4.00 header does not have them either:
 * SCE_OK, SCE_APP_CONTENT_ENTITLEMENT_KEY_SIZE, SCE_APP_CONTENT_PFT_FLAG_*,
 * SCE_APP_CONTENT_APPPARAM_ID_SKU_FLAG, SCE_APP_CONTENT_APPPARAM_SKU_FLAG_FULL,
 * SCE_APP_CONTENT_ADDCONT_DOWNLOAD_STATUS_INSTALLED and
 * SceAppContentAddcontInfo. src/dlc_modules/dlc_content.h supplies each one
 * behind an #ifndef, and defining them here would take a different branch of
 * that header than the Windows build takes. */

#define SCE_APP_CONTENT_ERROR_NOT_INITIALIZED    -2133262335 /* 0x80D90001 */
#define SCE_APP_CONTENT_ERROR_PARAMETER          -2133262334 /* 0x80D90002 */
#define SCE_APP_CONTENT_ERROR_BUSY               -2133262333 /* 0x80D90003 */
#define SCE_APP_CONTENT_ERROR_NOT_MOUNTED        -2133262332 /* 0x80D90004 */
#define SCE_APP_CONTENT_ERROR_NOT_FOUND          -2133262331 /* 0x80D90005 */
#define SCE_APP_CONTENT_ERROR_MOUNT_FULL         -2133262330 /* 0x80D90006 */
#define SCE_APP_CONTENT_ERROR_DRM_NO_ENTITLEMENT -2133262329 /* 0x80D90007 */
#define SCE_APP_CONTENT_ERROR_NO_SPACE           -2133262328 /* 0x80D90008 */
#define SCE_APP_CONTENT_ERROR_NOT_SUPPORTED      -2133262327 /* 0x80D90009 */
#define SCE_APP_CONTENT_ERROR_INTERNAL           -2133262326 /* 0x80D9000A */
#define SCE_APP_CONTENT_ERROR_DOWNLOAD_ENTRY_FULL -2133262325 /* 0x80D9000B */
#define SCE_APP_CONTENT_ERROR_INVALID_PKG        -2133262324 /* 0x80D9000C */
#define SCE_APP_CONTENT_ERROR_OTHER_APPLICATION_PKG -2133262323 /* 0x80D9000D */
#define SCE_APP_CONTENT_ERROR_CREATE_FULL        -2133262322 /* 0x80D9000E */
#define SCE_APP_CONTENT_ERROR_MOUNT_OTHER_APP    -2133262321 /* 0x80D9000F */
#define SCE_APP_CONTENT_ERROR_OF_MEMORY          -2133262320 /* 0x80D90010 */
#define SCE_APP_CONTENT_ERROR_ADDCONT_SHRANK     -2133262319 /* 0x80D90011 */
#define SCE_APP_CONTENT_ERROR_ADDCONT_NO_IN_QUEUE -2133262318 /* 0x80D90012 */
#define SCE_APP_CONTENT_ERROR_NETWORK            -2133262317 /* 0x80D90013 */
#define SCE_APP_CONTENT_ERROR_SIGNED_OUT         -2133262316 /* 0x80D90014 */
#define SCE_APP_CONTENT_ERROR_UNSUPPORTED_COMPRESSION_FORMAT -2133262315 /* 0x80D90015 */
#define SCE_APP_CONTENT_ERROR_BROKEN             -2133262314 /* 0x80D90016 */
#define SCE_APP_CONTENT_ERROR_ADDCONT_NO_SPACE   -2133262313 /* 0x80D90017 */
#define SCE_APP_CONTENT_ERROR_ADDCONT_ENFILE     -2133262312 /* 0x80D90018 */
#define SCE_APP_CONTENT_ERROR_ADDCONT_NO_APR_METADATA_MEMORY -2133262311 /* 0x80D90019 */

#define SCE_APP_CONTENT_APPPARAM_ID_USER_DEFINED_PARAM_1 (1)
#define SCE_APP_CONTENT_APPPARAM_ID_USER_DEFINED_PARAM_2 (2)
#define SCE_APP_CONTENT_APPPARAM_ID_USER_DEFINED_PARAM_3 (3)
#define SCE_APP_CONTENT_APPPARAM_ID_USER_DEFINED_PARAM_4 (4)

#define SCE_APP_CONTENT_MOUNTPOINT_DATA_MAXSIZE (16)
#define SCE_APP_CONTENT_ADDCONT_MOUNT_MAXNUM    (64)
#define SCE_APP_CONTENT_INFO_LIST_MAX_SIZE      (2500)

#define SCE_APP_CONTENT_TEMPORARY_DATA_OPTION_NONE   (0)
#define SCE_APP_CONTENT_TEMPORARY_DATA_OPTION_FORMAT (1 << 0)

typedef uint32_t SceAppContentMediaType;
typedef uint32_t SceAppContentBootAttribute;
typedef uint32_t SceAppContentAppParamId;
typedef uint32_t SceAppContentAddcontDownloadStatus;
typedef uint32_t SceAppContentTemporaryDataOption;

typedef struct SceAppContentInitParam {
    char reserved[32];
} SceAppContentInitParam;

typedef struct SceAppContentBootParam {
    char                       reserved1[4];
    SceAppContentBootAttribute attr;
    char                       reserved2[32];
} SceAppContentBootParam;

typedef struct SceAppContentMountPoint {
    char data[SCE_APP_CONTENT_MOUNTPOINT_DATA_MAXSIZE];
} SceAppContentMountPoint;

typedef struct SceAppContentAddcontDownloadProgress {
    uint64_t dataSize;
    uint64_t downloadedSize;
} SceAppContentAddcontDownloadProgress;

#endif
