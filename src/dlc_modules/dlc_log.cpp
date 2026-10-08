/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "dlc_log.h"

#if SCE_DLC_EMU_LOG

#include <_fs.h>
#include <_kernel.h>

#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

// Weak on purpose: a firmware that does not export it leaves this NULL rather
// than failing the module load. It needs a weak link stub to resolve at all --
// see the "kernel" entry in tools/make_dlc_ipmi_stub.py.
extern "C" __attribute__((weak)) void sceKernelDebugOutText(int dbg_channel, const char* text);

namespace {
constexpr int kLogMode = 0666;
constexpr int kLogFlags =
    SCE_KERNEL_O_WRONLY | SCE_KERNEL_O_CREAT | SCE_KERNEL_O_APPEND;

// The configured path is tried first so a build-time override always wins. It
// defaults to /app0, which is where this log wants to be: the game's own deploy
// directory, writable from inside the sandbox and readable over FTP afterwards
// with no collector involved.
//
// THE CLAIM THIS COMMENT USED TO MAKE WAS WRONG. It said /app0 "is the game
// image and is mounted READ-ONLY, so opening a log there fails". ShadowMountPlus
// mount_read_only applies to the IMAGE mounts it manages, not to the game's
// /app0 sandbox, and a later run measured the open succeeding every time.
// USER: "app0 is not read only."
//
// The remaining entries survive only as fallbacks for a build that overrides
// the path onto a mount that is not present. /download2 leads them because
// ShadowMountPlus backs it with a directory on /data.
//
// /temp0 IS DELIBERATELY NOT A CANDIDATE. It is deleted as the process exits
// and is unreadable in place over FTP (RETR 550, a uid refusal), so anything
// landing there needed an outside collector to rescue it -- and the cases most
// worth logging, a wedge or a hard power-off, never reach that collection.
const char* const kLogPaths[] = {
    SCE_DLC_EMU_LOG_PATH,
    "/download2/dlc_emu.log",
    "/download1/dlc_emu.log",
    "/download0/dlc_emu.log",
};

std::atomic<const char*> g_logPath{nullptr};
std::atomic<uint32_t> g_logPathState{0};

// Written directly to the fd, not through dlc_logf, which would recurse. Says
// which sink won and whether the klog sink resolved, so a silent log is
// diagnosable from the one line that does appear.
void write_banner(int fd, const char* path) {
    char line[256];
    const int len = std::snprintf(line,
                                  sizeof(line),
                                  "dlc.log open version=%s path=%s klog=%s\n",
                                  SCE_DLC_EMU_VERSION,
                                  path,
                                  sceKernelDebugOutText ? "yes" : "no");
    if (len > 0) {
        const size_t used =
            static_cast<size_t>(len) < sizeof(line) ? static_cast<size_t>(len) : sizeof(line) - 1u;
        (void)sceKernelWrite(fd, line, used);
    }
}

// First candidate that accepts an append-open, or nullptr when none do.
// Resolved once; concurrent callers wait rather than probing again.
const char* log_path() {
    uint32_t expected = 0;
    if (g_logPathState.compare_exchange_strong(expected,
                                               1u,
                                               std::memory_order_acq_rel,
                                               std::memory_order_acquire)) {
        const char* chosen = nullptr;
        for (const char* candidate : kLogPaths) {
            const int fd = sceKernelOpen(candidate, kLogFlags, kLogMode);
            if (fd >= 0) {
                chosen = candidate;
                write_banner(fd, candidate);
                (void)sceKernelClose(fd);
                break;
            }
        }
        g_logPath.store(chosen, std::memory_order_release);
        g_logPathState.store(2u, std::memory_order_release);
        return chosen;
    }
    while (g_logPathState.load(std::memory_order_acquire) != 2u) {
        __builtin_ia32_pause();
    }
    return g_logPath.load(std::memory_order_acquire);
}
}  // namespace

void dlc_logf(const char* fmt, ...) {
    if (!fmt || !*fmt) {
        return;
    }

    char line[768]{};
    va_list ap;
    va_start(ap, fmt);
    const int len = std::vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    if (len <= 0) {
        return;
    }

    size_t used = 0;
    while (used + 1 < sizeof(line) && line[used]) {
        ++used;
    }
    if (used + 1 < sizeof(line)) {
        line[used++] = '\n';
        line[used] = '\0';
    }

#if SCE_DLC_EMU_LOG_KERNEL_OUT
    if (sceKernelDebugOutText) {
        sceKernelDebugOutText(0, line);
    }
#endif

    const char* const path = log_path();
    if (!path) {
        return;
    }

    const int fd = sceKernelOpen(path, kLogFlags, kLogMode);
    if (fd < 0) {
        return;
    }
    (void)sceKernelWrite(fd, line, used);
    // FSYNCED, because the runs this log exists for end in a hard power off and
    // the last line is the deliverable. close() returns the fd, it does not
    // promise the bytes reached the medium; a tail still sitting in the cache
    // when the power goes is indistinguishable from a call that never happened.
    (void)sceKernelFsync(fd);
    (void)sceKernelClose(fd);
}

#endif
