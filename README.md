# offstage

**Background QA for macOS apps — while you keep using your Mac.**

offstage lets an AI agent (or a plain script) exercise and verify a native
macOS app _in the background_: it reads real structure through the
accessibility tree, captures real pixels with ScreenCaptureKit, presses
controls via `AXPress`, and verifies against ground truth (UserDefaults / a
semantic port) — with **zero synthetic input ever reaching your foreground**.
The app under test never becomes frontmost; you keep typing in your editor.

Measured results behind the design (single host, macOS 26.1): equal-or-better
defect recall than screenshot-based agents at 3.6–28× lower observation cost,
and a deterministic regression mode that catches seeded defects at 13/13 and
8/8 with 0 false alarms — using **zero model tokens**. See
[docs/channels.md](docs/channels.md) for the numbers and their limits.

## How it works

```
┌────────────┐   press / menu (AXPress)   ┌──────────────────┐
│  offstage  │ ─────────────────────────▶ │  app under test  │
│   driver   │   port (line-JSON/UNIX)    │   (background,   │
│            │ ─────────────────────────▶ │  never frontmost)│
│            │ ◀───────────────────────── │                  │
└────────────┘   AX tree · SCK pixels ·   └──────────────────┘
                 UserDefaults ground truth
```

- **Perceive** through the AX tree (`observe`) — ~1/20th the tokens of a
  screenshot, and it degrades more gracefully with smaller models.
- **Actuate** with `AXPress` (`press`, `menu`) — no synthetic events — and a
  **semantic port** the app embeds in debug builds
  ([OffstagePort](swift/OffstagePort)) for everything background AX can't do
  (typing, tab switching, drags).
- **Verify** against ground truth: `defaults export`, port state, and
  canonical-state pixel goldens (`golden`).

## Quick start

```sh
pip install -e .
offstage probes build       # compiles the Swift probe binaries (one-time)
offstage doctor             # checks session, permissions, toolchain
```

Try it on the bundled fixture app:

```sh
cd examples/NotesApp
xcodegen generate
xcodebuild -project NotesApp.xcodeproj -scheme NotesApp -configuration Debug \
  -derivedDataPath /tmp/offstage-nb-dd build
cd ..

offstage validate notesapp.manifest.json
offstage start notesapp.manifest.json
offstage press notesapp.manifest.json addNote
offstage observe notesapp.manifest.json
offstage port notesapp.manifest.json '{"cmd":"rename","index":0,"title":"Hello"}'
offstage golden bake notesapp.manifest.json   # bake canonical goldens (local!)
offstage golden check notesapp.manifest.json  # later: pixel-diff against them
offstage stop notesapp.manifest.json
```

Point it at your own app by writing a manifest
([docs/manifest.md](docs/manifest.md)) and embedding the port
([swift/OffstagePort](swift/OffstagePort)) behind `--uitest-port`.

## The deterministic batteries

[bench/](bench/) holds scripted probe batteries for the two fixture apps —
launch, a11y scan, journeys, edge inputs, persistence, canonical goldens, and
an app-never-frontmost safety check. They are the harness's integration tests
and a template for crystallizing your own app's journeys into a 0-token
regression gate (~30 s per run).

```sh
python3 bench/battery_notes.py baseline --make-golden   # first run bakes goldens
python3 bench/battery_notes.py check                    # 0-token regression gate
```

## Host requirements

- macOS 15+ (measured on 26.1), Xcode command-line tools; `xcodegen` for the
  example apps.
- **Unlocked screen, display awake** (`caffeinate -du` for long runs). The
  driver refuses to run into a locked session — channels degrade silently.
- **Accessibility** and **Screen Recording** permissions for the host
  terminal/process. These are one-time manual grants (System Settings >
  Privacy & Security); there is no programmatic way around them, including in
  CI — see [docs/limits.md](docs/limits.md).

## What this deliberately does not do

No synthetic keyboard/mouse events on a shared desktop, ever. No background
typing into SwiftUI fields (the AX set-value "success" is an illusion — the
store never changes). No golden portability across machines (byte-exact is
same-machine only). The full list of encoded lessons: [docs/limits.md](docs/limits.md).

## Repo layout

| path                   | what                                                        |
| ---------------------- | ----------------------------------------------------------- |
| `src/offstage/`        | Python driver + CLI (`offstage`), manifest validator        |
| `src/offstage/probes/` | single-file Swift probes (AX, SCK, pixdiff, session lock)   |
| `swift/OffstagePort/`  | Swift package: the semantic port apps embed in debug builds |
| `examples/`            | two fixture apps (NotesApp, ConvertApp) + manifests         |
| `bench/`               | deterministic probe batteries (= integration tests)         |
| `docs/`                | channel table, limits, manifest reference                   |

## Provenance

Extracted from a private research program on agentic macOS QA — channel
measurement, perception ablations, seeded-defect benchmarks. The
numbers quoted throughout are from those measured runs; where a rule looks
oddly specific, it's because violating it broke a run.

## License

MIT — see [LICENSE](LICENSE).
