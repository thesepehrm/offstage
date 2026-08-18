# Hard-won rules and known limits

Every rule here cost a broken run before it was understood. The harness encodes
them; this page explains why they exist so you don't relearn them.

## Host requirements (enforced or checked by `offstage doctor`)

1. **The screen must be unlocked and the display awake.** Under
   `CGSSessionScreenIsLocked = 1` a newly launched app produces empty AX trees,
   SCK captures fail to load, and `AXPress` stalls 5–36 s. "User away" is not
   the safe state; unlocked and awake is. The driver refuses to launch into a
   locked session; keep the display awake with `caffeinate -du` during runs.
2. **Accessibility permission** for the host process (System Settings >
   Privacy & Security > Accessibility). Without it, probes see empty trees.
3. **Screen Recording permission** for golden captures (ScreenCaptureKit).
4. A dedicated login session or machine **only** for journeys that need real
   key events (XCUITest replay). Everything offstage does day-to-day runs on a
   shared, in-use desktop.

## Rules the driver encodes

- **Crash residue is cleared before every launch.** After a crash, the
  CrashReporter flag plist and saved state make the next launch show the
  "unexpectedly quit, reopen windows?" modal, which hijacks AX scans, resize,
  and captures. (`-ApplePersistenceIgnoreState` would also prevent the dialog,
  but it suppresses window creation entirely for a background-launched SwiftUI
  WindowGroup app.)
- **Per-app appearance is pinned** (`-NSRequiresAquaSystemAppearance YES`): a
  system dark-mode switch flips ~80% of pixels and destroys every golden.
- **Harness launch flags are passed as `-key value` pairs** (`-uitest-port
<sock>`, `-uitest-reset 1`), never as bare `--flags`. AppKit strips `-key
value` pairs from the launch arguments, but treats leftover bare arguments
  as documents to open. Once three of them accumulate, a background-
  launched SwiftUI WindowGroup app never creates its window at all (observed
  macOS 26.1: `--uitest-reset --uitest-port /tmp/x.sock` launched an app with
  a menu bar, a live port, and zero windows). `AgentPort.fromLaunchArguments`
  and `AgentPort.resetRequested` accept both spellings so manual `--uitest-*`
  runs still work.
- **Goldens are appearance-, state-, and selection-scoped**, baked only from
  the manifest's canonical fixture recipe. Diffing against arbitrary session
  state confounds the check: a free agent cannot attribute the diff.
- **Golden thresholds must clear the first-run noise band (~0.08%).** The
  first capture after writing a golden differed by a stable 0.079% before
  later runs went byte-exact; "any nonzero pixel" false-alarms. 0.1% held.
  The manifest validator rejects thresholds inside the band.
- **Byte-exact goldens are same-machine only.** Portability across GPU
  families and OS updates is untested and assumed absent. Bake goldens
  locally, never commit them.
- **Capture prefers titled windows.** SwiftUI apps carry phantom untitled
  windows (tab-bar strips, ghosts) that can beat the content window on area
  alone and capture as blank.
- **A ≥50% golden diff is treated as a bogus capture**, not a visual change:
  SCK sometimes returns a blank frame right after a resize. The driver nudges
  a redraw (resize ±1 px) and recaptures once.
- **Verifiers read ground truth** (UserDefaults / the store behind the port),
  never only the actuation layer's echo. The port bypasses all UI input
  plumbing; claims built on its echo alone are model-level.
- **A launch that does not settle is fatal, and says which half failed.** The
  gate is the port answering plus an `AXWindow` in the tree, but a launch that
  misses it leaves the process RUNNING — so every later command drives a
  half-launched app whose port replies with the right route while presses find
  nothing. `start`/`restart` now fail their step (they used to return
  `launched=False` with no `ok` key, which the batch defaulted to ok and ran
  on from), the CLI exits nonzero, and `launch_note` names whether the ping or
  the `AXWindow` never came up. The timeout is 45 s: a cold launch under
  memory pressure was measured stalling its main thread for 30 s in one
  stretch, and the old 10 s ceiling reported that as an app that creates no
  window at all — it does; `CGWindowListCopyWindowInfo` and
  `kAXWindowsAttribute` both find the window on the very pid whose `axdump`
  is one bare `AXApplication` row.
- **An actuation probe that reports failure fails the step.** `axpress` prints
  `PRESS=FAIL` when neither the button nor the toolbar overflow matched and
  `axmenu` prints `ERROR: ...`; `_act` discarded their stdout and answered
  `done` regardless, so a journey of misses passed. The only tell was latency
  — axpress polls to a 1.5 s deadline, so a miss answers in ~1600 ms where a
  landing press answers in ~100 ms. Latency is still the only tell for a press
  that lands on the WRONG element.

## Known limits

- Custom-drawn views without AX exposure are invisible to the AX channels;
  treat missing AX exposure as a bug in the app under test (it also breaks
  VoiceOver users).
- Timing: poll postconditions with a timeout instead of fixed sleeps where you
  can. Measured action → AX-tree-settled p50 38 ms, p95 56 ms, so a fixed
  0.6 s settle spent an order of magnitude more than the work needed and still
  only guessed. The driver now settles on a `offstage.ping` port round-trip
  (the reply crosses `DispatchQueue.main.sync`, so it proves the main-thread
  work queued by the action has run) and waits for launch on port-answers plus
  an `AXWindow` in the tree. Apps with no port fall back to the flat sleep.
- **A settled main thread is not a settled AX tree.** The tree publishes
  asynchronously afterwards, so a control an action just revealed can be
  absent for tens of ms (p95 56 ms). `axpress` polls for its target to a
  1.5 s deadline for that reason; any probe that looks for a control once,
  immediately after an action, will flake instead of failing honestly.
- Order-sensitive defects (stale recompute after a specific journey order)
  favor crystallized deterministic probes over free agents; both blind-agent
  arms missed one that the battery catches explicitly.
- Complementary blindness: pixels miss semantics (accessibility-label defects
  are not pixels); text misses typography (font regressions need the
  canonical-state golden check). Run both.
- **Several builds of one app share its identity.** Worktrees, or a release
  build beside a debug one, put several same-named processes with the same
  bundle id on the machine. The driver keeps its own instance apart by the
  socket path it launched with (falling back to the app bundle path), targets
  the AX probes at that pid rather than the bundle id, and launches with
  `open -n` so LaunchServices cannot hand back somebody else's copy. When
  neither marker matches, one same-named process running is still taken as the
  target for read-only questions (liveness, the AX target) — but never for a
  kill: that case is reached exactly when this manifest's instance is _not_
  running, so the single candidate belongs to somebody else. `stop` says
  `not stopped` and quits nothing instead. Three things stay outside its
  reach, and `start`/`observe` report the other instances so they are at least
  visible:
  - `defaults export` reads one preferences domain for all of them, so ground
    truth is whichever copy wrote last.
  - An `xcodebuild test` run in another checkout terminates every instance —
    the app is the test host.
  - So does an `offstage start` from another checkout's session.
