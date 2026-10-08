# Android example — Glove Viewer

Reads a Proception Glove over USB OTG and draws the taxels live. One activity,
no dependencies beyond the SDK and the Android framework, so the whole API fits
in one readable file.

## Build

Open `glove_viewer/` in Android Studio and run it, or from the command line
with your own Gradle (8.13 or newer) and JDK 17:

```sh
cd glove_viewer
gradle assembleDebug
adb install -r build/outputs/apk/debug/glove_viewer-debug.apk
```

The project takes the SDK from `../../proglove_sdk/android/aar/`, so it builds
straight out of this package with nothing to download from us.

Requirements: an arm64 Android device with USB host support, API 24 or newer,
and a USB OTG adapter.

## Using it

1. Start the app. It reports "no glove attached".
1. Plug the glove in. It appears in the device list.
1. Tap **Allow** on the USB permission dialog. The app opens the device, starts
   the stream, and keeps the heartbeat going.
1. Press a taxel and watch it light up.

Buttons: **Perm** re-asks for USB permission, **Zero** takes a new baseline
with the hand at rest, **Filt** switches between filtered and raw values, and
**Hand**/**Grid** switches the view.

`adb logcat -s ProGloveSdk` prints a status line every two seconds:

```
status=connected devices=1 handedness=ok frames=842 hz=99.3 peak=1204 error=none
```

## What to copy

| File | What it shows |
|---|---|
| `MainActivity.java` | Opening a glove, polling it, and reading frames |
| `GloveHandView.java` | Drawing taxels at their real positions on the hand |
| `TaxelGridView.java` | The simplest possible view of the same data |

The SDK API itself is three calls: `GloveChannel.open()`, `poll()` on a timer,
and the `Listener` you pass it. See `../../docs/ANDROID.md` for the protocol
underneath, and `../../proglove_sdk/android/README.md` for the package layout.
