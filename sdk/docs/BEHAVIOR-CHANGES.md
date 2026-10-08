# Behavior Changes

What changes for you between releases, and what you have to do about it. Only
things that alter behavior or require a code change appear here — see the
per-component changelogs for the full history.

______________________________________________________________________

## Unreleased — ProHand SDK 0.4.x

Two breaking API changes, both in hand commands, and a new monitoring surface.
The wire format is unchanged, so **this release does not require a firmware
update**. Rebuild against the new headers and library together: the Python
wrapper checks struct sizes against the loaded library at import and will refuse
to start on a mismatch rather than misread your data.

### Breaking: hand-command torque is now per joint

`prohand_send_hand_command()` and `prohand_send_hand_streams()` took a single
`float torque` applied to all 20 joints. They now take `const float *torques` —
20 values, same thumb-to-pinky order as `positions`.

`HandCommand` has always carried one torque per joint on the wire; firmware
accepted them and the Cap'n Proto client exposed five. Only this SDK collapsed
them to one, so per-finger grip was unreachable from C, C++ and Python.

**What to do.** In Python and C++, nothing — a scalar still works and expands
internally:

```python
client.send_hand_command(pos, 0.45)                        # unchanged
client.send_hand_command(pos, [0.2, 0.6, .45, .45, .45])   # per finger, new
client.send_hand_command(pos, [...20 values...])           # per joint, new
```

In C, build the array:

```c
float torques[20];
for (int i = 0; i < 20; i++) torques[i] = 0.45f;
prohand_send_hand_command(client, positions, torques, velocity);
```

### Breaking: `velocity_saturation` is normalized 0.0–1.0

It was a raw `0–255` count here while the Cap'n Proto client took a normalized
float and scaled it — the same parameter meaning two different things depending
on which client you used. Both are normalized now. `0.0` still selects the
firmware default.

**What to do.** If you passed raw counts, divide by 255. A value of `50` now
means "clamp to 1.0", i.e. full speed — the opposite of what you intended, and
it will not error. This is the one change that fails silently, so grep for your
call sites.

It remains per-hand: the wire carries a single value for all fingers.

### Fixed: alerts arrived with `thermal_event` unset

Every alert crossing the IPC boundary had `thermal_event` set to `None`,
regardless of what firmware sent. A thermal warning was indistinguishable from a
thermal lockdown from a non-thermal alert — only `severity` survived. The field
was written by the parser but never by the encoder.

**What to do.** Nothing, but if you built logic around `severity` alone because
`thermal_event` looked useless, `thermal_event` is now trustworthy and more
specific.

### Fixed: heartbeat age was seeded at client creation

`prohand_ms_since_last_heartbeat()` started its clock when you constructed the
client, not when the first status arrived. With no driver running it reported a
small, steadily-growing age — indistinguishable from a healthy link. A watchdog
comparing it against a threshold saw a live hand that was never there.

It now writes `UINT64_MAX` until a status message actually arrives, the same
sentinel `prohand_get_system_status()` uses for `ms_since_heartbeat`. The call
still returns success, so nothing new to error-check.

The socket connecting no longer counts as a heartbeat either: an `ipc://`
subscribe succeeds even with no publisher on the other end, so it proved nothing.

**What to do.** If you compare the value against a timeout, `UINT64_MAX` exceeds
it and you will correctly treat the link as down. If you feed it to anything that
would be surprised by a very large number — an average, a plot, a subtraction —
special-case the sentinel.

### New: system status, signal rates and monitoring events

A single thermal alert carries no severity. Firmware raises one the moment a
temperature sample lands in a narrow band, so bus noise produces a stream of
them that reads like a hardware fault when it is not. Three additions make that
distinguishable:

**`prohand_get_system_status()`** — liveness, hand state, handedness, thermal
load and alert rates in one passive read. Never consumes a status message or
sends a command, so it is safe to poll from a UI at frame rate. Start here.

**`prohand_get_thermal_load()` / `prohand_get_signal_rates()`** — the breakdown.
Rates are a percentage of the maximum rate firmware can publish for that signal,
so a lone excursion reads ~8% and a persistent fault saturates at 100%.

**`prohand_poll_system_event()`** — qualified events. A thermal warning has to
persist across at least two firmware re-assertions (~12 s) before
`ThermalWarningConfirmed` is raised; a single noisy sample never produces one.
`ThermalLockdown` is never debounced.

```python
for event in client.drain_events():
    if event.kind is SystemEventKind.THERMAL_LOCKDOWN:
        stop_motion()
```

**The status stream is not filtered.** Everything the driver publishes still
reaches `try_recv_message()`, so anything doing its own diagnostics keeps seeing
every alert first-hand. Events run alongside it, not in front of it.

Counts start when your client connects; nothing carries prior history across the
socket.

### Changed: the driver is quieter in release builds

Warning-severity alerts now log at debug rather than warn in a release build, so
thermal chatter no longer fills the console. Error severity is untouched — a real
thermal lockdown still prints. The alert itself is published either way; only the
driver's own logging changed.

### See also

`just sdk demo python show-all` prints every value the SDK exposes — status,
rates, events and each decoded frame kind — in one read-only dashboard. It sends
no commands.
