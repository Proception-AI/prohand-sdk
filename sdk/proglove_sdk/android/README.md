# Proception Glove — Android

Native protocol library and C API for reading a Proception Glove on Android
over USB OTG.

```
android/
├── include/
│   └── glove_proto.h                 # C API (generated)
└── jni/
    └── arm64-v8a/
        └── libglove_proto.so         # Protocol library, Android arm64
```

Unlike the desktop bindings in this SDK, the Android path needs no host
process: your application opens the USB device with `UsbManager`, and the
library turns the bytes into decoded tactile and IMU frames.

See [`../../docs/ANDROID.md`](../../docs/ANDROID.md) for the USB properties,
the call sequence, the data layout, and the common failures.
