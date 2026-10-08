/**
 * ProWristCam Client SDK - C API
 *
 * This header provides a minimal C interface to the WristCam Client SDK.
 *
 * Usage:
 * 1. Create a client with prowristcam_client_create()
 * 2. Poll JPEG frames with prowristcam_try_recv_frame()
 * 3. Free each frame's JPEG buffer with prowristcam_free_frame()
 * 4. Clean up with prowristcam_client_destroy()
 *
 * Linking:
 * - Link against libprowristcam_client_sdk.so (Linux),
 *   libprowristcam_client_sdk.dylib (macOS), or prowristcam_client_sdk.dll
 *   (Windows).
 * - The library is typically located in ../lib/ relative to this header.
 *
 * Thread Safety: The client handle is NOT thread-safe. Use external
 * synchronization if accessing from multiple threads.
 *
 * Version: 0.1.0
 */

#ifndef PROWRIST_SDK_H
#define PROWRIST_SDK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* TYPES AND STRUCTURES */
/* ========================================================================== */

/**
 * Opaque handle to a WristCam client instance.
 */
typedef struct WristCamClientHandle WristCamClientHandle;

/**
 * Result codes returned by SDK functions.
 */
typedef enum {
  PROWRISTCAM_SUCCESS = 0,
  PROWRISTCAM_ERROR_NULL = -1,
  PROWRISTCAM_ERROR_CONNECTION = -2,
  PROWRISTCAM_ERROR_INVALID_ARGUMENT = -3,
  PROWRISTCAM_ERROR_OTHER = -99
} WristCamResult;

/**
 * JPEG frame received from the wrist camera.
 *
 * When `is_valid == 1` after a successful call to prowristcam_try_recv_frame(),
 * `jpeg_data` points to `jpeg_len` bytes of raw JPEG data.
 *
 * The caller **must** call prowristcam_free_frame() to release `jpeg_data`.
 * After prowristcam_free_frame() returns, `jpeg_data` is set to NULL.
 */
typedef struct {
  int is_valid;       /**< 1 if a frame is present, 0 otherwise */
  uint32_t uid;       /**< Rolling frame counter (packet-loss detection) */
  uint64_t timestamp; /**< Capture timestamp — milliseconds since UNIX epoch */
  uint32_t width;     /**< Frame pixel width as reported by the camera driver */
  uint32_t height; /**< Frame pixel height as reported by the camera driver */
  uint8_t *jpeg_data; /**< Heap-allocated JPEG bytes; free with
                         prowristcam_free_frame() */
  uint32_t jpeg_len;  /**< Length of jpeg_data in bytes */
} WristCamFrameInfo;

/* ========================================================================== */
/* CLIENT LIFECYCLE */
/* ========================================================================== */

/**
 * Create a new WristCam IPC client.
 *
 * Subscribes to the given ZeroMQ PUB endpoint.  Connection is established
 * asynchronously; use prowristcam_client_is_connected() to confirm.
 *
 * @param stream_endpoint  ZMQ endpoint of the wrist-camera publisher, e.g.
 *                         "ipc:///tmp/prowristcam-left-stream.ipc"
 *                         "tcp://127.0.0.1:5565"
 * @return  Pointer to client handle on success, NULL on failure.
 *
 * Example:
 *   WristCamClientHandle *client = prowristcam_client_create(
 *       "ipc:///tmp/prowristcam-left-stream.ipc"
 *   );
 */
WristCamClientHandle *prowristcam_client_create(const char *stream_endpoint);

/**
 * Destroy a WristCam client handle and free all resources.
 *
 * @param handle  Client handle to destroy.
 */
void prowristcam_client_destroy(WristCamClientHandle *handle);

/**
 * Check if the client is connected to the stream publisher.
 *
 * @param handle  Client handle.
 * @return  1 if connected, 0 if not.
 */
int prowristcam_client_is_connected(const WristCamClientHandle *handle);

/* ========================================================================== */
/* FRAME RECEPTION */
/* ========================================================================== */

/**
 * Try to receive the next JPEG frame (non-blocking).
 *
 * Heartbeat / ping messages are skipped automatically.  Returns immediately
 * if no frame is queued.
 *
 * On success (`return == 1`):
 *   - `out_frame->is_valid`   is set to 1
 *   - `out_frame->uid`        is the rolling frame counter (u32)
 *   - `out_frame->timestamp`  is milliseconds since UNIX epoch (u64)
 *   - `out_frame->width`      is the frame pixel width
 *   - `out_frame->height`     is the frame pixel height
 *   - `out_frame->jpeg_data`  points to `out_frame->jpeg_len` freshly
 *                             heap-allocated bytes.
 *
 * The caller **must** call prowristcam_free_frame(out_frame) when done with
 * the JPEG data.
 *
 * @param handle     Client handle.
 * @param out_frame  Output structure to fill.
 * @return  1 if a frame was received, 0 if no frame is available,
 *          or a negative WristCamResult on error.
 *
 * Example:
 *   WristCamFrameInfo frame = {0};
 *   if (prowristcam_try_recv_frame(client, &frame) > 0) {
 *       printf("Frame uid=%u ts=%llu %ux%u size=%u bytes\n",
 *              frame.uid, (unsigned long long)frame.timestamp,
 *              frame.width, frame.height, frame.jpeg_len);
 *       // process frame.jpeg_data ...
 *       prowristcam_free_frame(&frame);
 *   }
 */
int prowristcam_try_recv_frame(const WristCamClientHandle *handle,
                               WristCamFrameInfo *out_frame);

/**
 * Free JPEG data allocated by prowristcam_try_recv_frame().
 *
 * Sets `frame->jpeg_data` to NULL and `frame->jpeg_len` to 0.
 *
 * @param frame  Pointer to a WristCamFrameInfo previously populated by
 *               prowristcam_try_recv_frame().
 */
void prowristcam_free_frame(WristCamFrameInfo *frame);

/* ========================================================================== */
/* VERSION INFO */
/* ========================================================================== */

/**
 * Get the library version string.
 *
 * @return  Null-terminated version string (do not free).
 */
const char *prowristcam_get_version(void);

#ifdef __cplusplus
}
#endif

#endif /* PROWRIST_SDK_H */
