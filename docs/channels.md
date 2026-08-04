# Background-safe channels

An agent can perceive and partially drive a macOS app **while the app stays in
the background and a user actively uses the same desktop** — with no synthetic
input ever reaching the user's foreground app. These are the channels offstage
composes (all measured on a single host, macOS 26.1, n=20 per channel unless
noted):

| need                           | channel                           | measured                                                                   |
| ------------------------------ | --------------------------------- | -------------------------------------------------------------------------- |
| structure / state              | AX tree read (`axdump`, `axscan`) | attach + full read p50 8 ms; pruned-tree diff ~21 tokens                   |
| composited pixels              | ScreenCaptureKit window capture   | p50 41 ms, works occluded, 20/20 captures byte-identical on a static scene |
| press / click                  | `AXPress` (`axpress`, `axmenu`)   | works on a background app, no synthetic events                             |
| typing / tab switching / drags | **semantic port** (OffstagePort)  | round-trip p50 0.04 ms; the only reliable background channel for these     |
| ground truth                   | `defaults export` (UserDefaults)  | verifiers read the store, never the actuation layer's echo alone           |
| session safety                 | `CGSSessionCopyCurrentDictionary` | locked screen = degraded channels; refuse to run                           |

## What is deliberately NOT in the set

- **No background typing channel exists for SwiftUI.** AX `kAXValueAttribute`
  set-value is an illusion: the field displays the value and AX reports it, but
  the binding and the persisted store never change. Real key events require a
  dedicated session; offstage routes typing through the semantic port instead.
- **No synthetic events on a shared desktop, ever.** `CGEvent` key events reach
  the target's queue with `window == nil`; AppKit/SwiftUI dispatch requires
  real active-window state. Event-injecting XCUITest lands keystrokes in
  whatever is frontmost — including the user's browser URL bar (observed).
  Idle-gating is not sufficient; journeys that need real events need a
  dedicated login session or machine, full stop.
- **`CALayer.render(in:)` is not a capture channel.** Its Metal region comes
  back transparent-empty and vibrancy renders flat gray — it re-executes CG
  drawing, it does not read the composited frame. ScreenCaptureKit is the only
  valid way to read composited pixels.
- **SwiftUI TabView tabs (and AppKit control tracking loops, WindowServer drag
  sessions) refuse background `AXPress`.** A blind agent will misread the
  unswitchable tab as an app defect. Route cross-tab state through the port and
  say so in agent task cards.

## Numbers worth quoting

All measured, single host, macOS 26.1, in the research program this harness was extracted from:

- Deterministic battery recall: 13/13 (notes app) and 8/8 (converter), 0 false
  alarms in 57 clean probe outcomes, ~30 s/variant, **0 model tokens**.
- Blind-agent arms (AX/ground-truth text vs screenshots): equal or better
  defect recall at 3.6–28× lower observation token cost; the advantage grows
  as the model shrinks.
- Whole-session cost still favors the text arm (19–31%) — orchestration
  dominates outside observations.
