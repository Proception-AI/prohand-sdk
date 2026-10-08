/**
 * ProGlove Client SDK - C API
 *
 * This header provides a minimal C interface to the ProGlove Client SDK.
 *
 * Usage:
 * 1. Create a client with proglove_client_create()
 * 2. Poll status with proglove_try_recv_status()
 * 3. Clean up with proglove_client_destroy()
 *
 * Linking:
 * - Link against libproglove_client_sdk.so (Linux),
 * libproglove_client_sdk.dylib (macOS), or proglove_client_sdk.dll (Windows)
 * - The library is typically located in ../lib/ relative to the header
 * directory
 *
 * Thread Safety: The client handle is NOT thread-safe. Use external
 * synchronization if accessing from multiple threads.
 *
 * Version: 0.1.0
 */

#include <stddef.h>
#include <stdint.h>

#ifndef PROGLOVE_SDK_H
#define PROGLOVE_SDK_H

#ifdef __cplusplus
extern "C" {
#endif

/* ========================================================================== */
/* TYPES AND STRUCTURES */
/* ========================================================================== */

/**
 * Opaque handle to a ProGlove client instance
 */
typedef struct ProGloveClientHandle ProGloveClientHandle;

/**
 * Result codes returned by SDK functions
 */
typedef enum {
  PROGLOVE_SUCCESS = 0,
  PROGLOVE_ERROR_NULL = -1,
  PROGLOVE_ERROR_CONNECTION = -2,
  PROGLOVE_ERROR_INVALID_ARGUMENT = -3,
  PROGLOVE_ERROR_NOT_CONNECTED = -4,
  PROGLOVE_ERROR_UNSUPPORTED = -5,
  PROGLOVE_ERROR_OTHER = -99
} ProGloveResult;

/**
 * USB device information
 */
typedef struct {
  const char *port_name;    /* Path to device - must be freed with
                               proglove_free_string() */
  const char *display_name; /* Display name with serial info - must be freed
                               with proglove_free_string() */
} ProGloveUsbDeviceInfo;

/* Taxel array sizes per segment (from taxel_mapping_v0.yaml) */
/* Thumb segments (larger than other fingers) */
#define PROGLOVE_TAXELS_T_DIP 6
#define PROGLOVE_TAXELS_T_MCP 10
#define PROGLOVE_TAXELS_T_PIP 4
/* Index finger segments */
#define PROGLOVE_TAXELS_I_DIP 4
#define PROGLOVE_TAXELS_I_MCP 2
#define PROGLOVE_TAXELS_I_PIP 2
/* Middle finger segments */
#define PROGLOVE_TAXELS_M_DIP 4
#define PROGLOVE_TAXELS_M_MCP 2
#define PROGLOVE_TAXELS_M_PIP 2
/* Ring finger segments */
#define PROGLOVE_TAXELS_R_DIP 4
#define PROGLOVE_TAXELS_R_MCP 2
#define PROGLOVE_TAXELS_R_PIP 2
/* Pinky finger segments */
#define PROGLOVE_TAXELS_P_DIP 4
#define PROGLOVE_TAXELS_P_MCP 2
#define PROGLOVE_TAXELS_P_PIP 2
/* Palm segments */
#define PROGLOVE_TAXELS_UPPER_PALM 16
#define PROGLOVE_TAXELS_MIDDLE_PALM 16
#define PROGLOVE_TAXELS_LOWER_PALM 16

/**
 * Tactile status from glove sensors (segment-based, u16 taxels, 12-bit ADC)
 *
 * Contains tactile pressure values organized by joint segment.
 * Each finger has DIP (distal), MCP (metacarpal), and PIP (proximal) segments.
 * Values are 0-4095, where higher values indicate more pressure.
 *
 * Segment sizes (from taxel_mapping_v0.yaml):
 * - Thumb: DIP(6) + MCP(10) + PIP(4) = 20 taxels
 * - Index/Middle/Ring/Pinky: DIP(4) + MCP(2) + PIP(2) = 8 taxels each
 * - Palm: upper(16) + middle(16) + lower(16) = 48 taxels
 * - Total: 100 taxels per hand
 */
typedef struct {
  int is_valid;           /* 1 if data is valid, 0 otherwise */
  unsigned int timestamp; /* Timestamp (milliseconds, wrapped) */
  unsigned int uid;       /* Unique identifier for this sample */
  /* Thumb segments (6+10+4 = 20 taxels) */
  uint16_t t_dip[PROGLOVE_TAXELS_T_DIP];
  uint16_t t_mcp[PROGLOVE_TAXELS_T_MCP];
  uint16_t t_pip[PROGLOVE_TAXELS_T_PIP];
  /* Index finger segments (4+2+2 = 8 taxels) */
  uint16_t i_dip[PROGLOVE_TAXELS_I_DIP];
  uint16_t i_mcp[PROGLOVE_TAXELS_I_MCP];
  uint16_t i_pip[PROGLOVE_TAXELS_I_PIP];
  /* Middle finger segments (4+2+2 = 8 taxels) */
  uint16_t m_dip[PROGLOVE_TAXELS_M_DIP];
  uint16_t m_mcp[PROGLOVE_TAXELS_M_MCP];
  uint16_t m_pip[PROGLOVE_TAXELS_M_PIP];
  /* Ring finger segments (4+2+2 = 8 taxels) */
  uint16_t r_dip[PROGLOVE_TAXELS_R_DIP];
  uint16_t r_mcp[PROGLOVE_TAXELS_R_MCP];
  uint16_t r_pip[PROGLOVE_TAXELS_R_PIP];
  /* Pinky finger segments (4+2+2 = 8 taxels) */
  uint16_t p_dip[PROGLOVE_TAXELS_P_DIP];
  uint16_t p_mcp[PROGLOVE_TAXELS_P_MCP];
  uint16_t p_pip[PROGLOVE_TAXELS_P_PIP];
  /* Palm segments (16+16+16 = 48 taxels) */
  uint16_t upper_palm[PROGLOVE_TAXELS_UPPER_PALM];
  uint16_t middle_palm[PROGLOVE_TAXELS_MIDDLE_PALM];
  uint16_t lower_palm[PROGLOVE_TAXELS_LOWER_PALM];
} ProGloveTactileStatus;

/**
 * IMU status - fused orientation quaternion from the on-board IMU
 */
typedef struct {
  int is_valid;           /* 1 if data is valid, 0 otherwise */
  unsigned int timestamp; /* Timestamp (milliseconds, wrapped) */
  float qw;
  float qx;
  float qy;
  float qz;
} ProGloveImuStatus;

/**
 * Tunable tactile filter parameters - deadzone sensitivity, stuck-pixel
 * spatial-isolation threshold, and stuck-detection timing. Fetch sensible
 * starting values with proglove_get_default_filter_config(), tweak only the
 * fields you care about, then apply with proglove_set_filter_config() - the
 * underlying command replaces the whole config, not a per-field patch.
 */
typedef struct {
  float deadzone_on;   /* Fraction of ADC max above which a taxel activates
                          (0.0-1.0) */
  float deadzone_off;  /* Fraction of ADC max below which an active taxel turns
                          off (0.0-1.0) */
  int denoise_enabled; /* Stuck-pixel masking on/off */
  unsigned short stuck_spatial_threshold; /* Raw ADC counts a taxel must exceed
                                              its segment neighbors' median by
                                              to count as spatially isolated */
  unsigned int stuck_streak_on_frames;    /* Consecutive flat+isolated frames
                                              before flagging stuck, at ~100 Hz */
} ProGloveFilterConfig;

/**
 * Called after each OTA page is flashed, with the running page count and
 * the total page count, so callers can drive a progress bar. `user_data` is
 * passed through unchanged from proglove_perform_ota() - use it for a
 * context/`this` pointer. Called synchronously on the calling thread; must
 * not call back into the client.
 */
typedef void (*ProGloveOtaProgressCallback)(unsigned int pages_sent,
                                            unsigned int total_pages,
                                            void *user_data);

/* ========================================================================== */
/* CLIENT LIFECYCLE */
/* ========================================================================== */

/**
 * Create a new ProGlove IPC client
 *
 * @param status_endpoint ZeroMQ endpoint for status (e.g.,
 * "ipc:///tmp/proglove-left-status.ipc")
 * @return Pointer to client handle on success, NULL on failure
 *
 * Example:
 *   ProGloveClientHandle* client = proglove_client_create(
 *       "ipc:///tmp/proglove-left-status.ipc"
 *   );
 */
ProGloveClientHandle *proglove_client_create(const char *status_endpoint);

/**
 * Destroy a ProGlove client handle and free resources
 *
 * @param handle Client handle to destroy
 */
void proglove_client_destroy(ProGloveClientHandle *handle);

/**
 * Check if client is connected to the device
 *
 * @param handle Client handle
 * @return 1 if connected, 0 if not connected
 */
int proglove_client_is_connected(const ProGloveClientHandle *handle);

/* ========================================================================== */
/* COMMAND FUNCTIONS */
/* ========================================================================== */

/**
 * Send a ping command to verify connection
 *
 * Since ProGlove uses PUB/SUB (not REQ/REP like ProHand), this method
 * waits for tactile data to be received, confirming the connection is working.
 *
 * @param handle Client handle
 * @return PROGLOVE_SUCCESS on success, PROGLOVE_ERROR_OTHER on failure
 */
ProGloveResult proglove_send_ping(const ProGloveClientHandle *handle);

/**
 * Full OTA update: sends the image size + key/sig, then answers every
 * firmware page request with the corresponding 256-byte chunk of `image`
 * (the final short page is padded with 0xFF), calling `progress_cb` after
 * each page. Blocks until the transfer succeeds, fails, or stalls for
 * timeout_ms with no reply (the timeout resets on every reply, so it's a
 * stall detector, not a cap on total transfer time).
 *
 * @param handle Client handle
 * @param image Firmware image bytes
 * @param image_len Firmware image size in bytes
 * @param key 32-byte ed25519 public key (currently unenforced firmware-side)
 * @param sig 64-byte ed25519 signature (currently unenforced firmware-side)
 * @param timeout_ms Milliseconds to wait for each firmware reply before giving
 * up
 * @param progress_cb Optional callback invoked after each page is sent (may be
 * NULL)
 * @param user_data Passed through unchanged to progress_cb
 * @return 1 on success, 0 on firmware-reported error or timeout, negative on
 * a client-side error (see ProGloveResult)
 */
int proglove_perform_ota(const ProGloveClientHandle *handle,
                         const uint8_t *image, size_t image_len,
                         const uint8_t *key, const uint8_t *sig,
                         unsigned int timeout_ms,
                         ProGloveOtaProgressCallback progress_cb,
                         void *user_data);

/**
 * Full calibration cycle, blocking until BaselineCommitted arrives or
 * timeout_ms elapses.
 *
 * @return 1 if calibration completed within the timeout, 0 if it timed out,
 * negative on error.
 */
int proglove_calibrate_and_wait(const ProGloveClientHandle *handle,
                                unsigned int timeout_ms);

/**
 * Toggle stuck-pixel masking.
 *
 * @param handle Client handle
 * @param enabled Non-zero to enable, zero to disable
 */
ProGloveResult proglove_set_denoise_enabled(const ProGloveClientHandle *handle,
                                            int enabled);

/**
 * Fill `out` with the default filter configuration.
 *
 * @param out Non-null pointer to a ProGloveFilterConfig to populate
 */
ProGloveResult proglove_get_default_filter_config(ProGloveFilterConfig *out);

/**
 * Replace the driver's entire tactile filter configuration.
 *
 * @param handle Client handle
 * @param config Non-null pointer to the desired configuration
 */
ProGloveResult proglove_set_filter_config(const ProGloveClientHandle *handle,
                                          const ProGloveFilterConfig *config);

/* ========================================================================== */
/* USB DISCOVERY */
/* ========================================================================== */

/**
 * Discover connected ProGlove USB devices
 *
 * Enumerates USB devices that match ProGlove identification patterns.
 * Looks for devices with serial numbers starting with "PRO-G" or "02D".
 *
 * @param out_devices Output array to store device info
 * @param max_devices Maximum number of devices to return
 * @return Number of devices found, or negative error code
 *
 * Note: Call proglove_free_string() on port_name and display_name for each
 * device.
 *
 * Example:
 *   ProGloveUsbDeviceInfo devices[10];
 *   int count = proglove_discover_usb_devices(devices, 10);
 *   for (int i = 0; i < count; i++) {
 *       printf("Device: %s\n", devices[i].display_name);
 *       proglove_free_string((char*)devices[i].port_name);
 *       proglove_free_string((char*)devices[i].display_name);
 *   }
 */
int proglove_discover_usb_devices(ProGloveUsbDeviceInfo *out_devices,
                                  int max_devices);

/**
 * Free a string allocated by the library
 *
 * @param s String pointer to free
 */
void proglove_free_string(char *s);

/* ========================================================================== */
/* STATUS POLLING */
/* ========================================================================== */

/**
 * Try to receive tactile status (non-blocking)
 *
 * @param handle Client handle
 * @param out_status Output structure to fill with tactile data
 * @return 1 if status was received, 0 if no status available, negative on error
 *
 * Example:
 *   ProGloveTactileStatus status;
 *   if (proglove_try_recv_status(client, &status) > 0) {
 *       if (status.is_valid) {
 *           printf("Thumb DIP[0]: %d\n", status.t_dip[0]);
 *       }
 *   }
 */
int proglove_try_recv_status(const ProGloveClientHandle *handle,
                             ProGloveTactileStatus *out_status);

/**
 * Try to receive a pre-filter RAW tactile frame (non-blocking).
 *
 * Same layout as proglove_try_recv_status(), but pure hardware ADC from the
 * driver's secondary raw node (no host filter/baseline). Poll it alongside
 * proglove_try_recv_status() to capture raw + processed together.
 *
 * @param handle Client handle
 * @param out_status Output structure to fill with raw tactile data
 * @return 1 if a raw frame was received, 0 if none available (or no raw node),
 * negative on error
 */
int proglove_try_recv_raw_tactile(const ProGloveClientHandle *handle,
                                  ProGloveTactileStatus *out_status);

/**
 * Whether this client derived a raw tactile endpoint (a local -status.ipc
 * path). 1 = subscribed to the raw node, 0 = none (e.g. a TCP endpoint).
 *
 * @param handle Client handle
 * @return 1 if a raw endpoint is subscribed, 0 if not, negative on error
 */
int proglove_has_raw_tactile(const ProGloveClientHandle *handle);

/**
 * Try to receive IMU status (non-blocking)
 *
 * @param handle Client handle
 * @param out_status Output structure to fill with IMU data
 * @return 1 if the next message was IMU data, 0 if no status available or
 * the next message was a different type, negative on error
 */
int proglove_try_recv_imu_status(const ProGloveClientHandle *handle,
                                 ProGloveImuStatus *out_status);

/* ========================================================================== */
/* VERSION INFO */
/* ========================================================================== */

/**
 * Get library version string
 *
 * @return Version string (do not free)
 */
const char *proglove_get_version(void);

#ifdef __cplusplus
}
#endif

#endif /* PROGLOVE_SDK_H */
