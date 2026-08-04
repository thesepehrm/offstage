# offstage

**Background QA for macOS apps — while you keep using your Mac.**

offstage lets an AI agent (or a plain script) drive and verify a native macOS
app without taking over your desktop. The app under test stays in the
background, never becomes frontmost, and no synthetic input ever reaches your
foreground.

What the agent gets:

- **Structure**: the accessibility tree, as compact text (`observe`).
- **Pixels**: real ScreenCaptureKit window captures — on-demand screenshots
  (`observe --mode screenshot`) and canonical-state golden diffs (`golden`).
- **Control**: button and menu presses via `AXPress` (`press`, `menu`), plus a
  semantic port the app embeds in debug builds for what background AX can't do
  — typing, tab switching, drags (`port`).
- **Ground truth**: the app's persisted state via `defaults export`, so
  verification never rests on what the UI merely claims.

The one thing it refuses: synthetic keyboard/mouse events on a shared desktop.
Those land in whatever window is frontmost — including yours.

## Why this beats a computer-use agent

A screenshot-driven computer-use agent needs the foreground: it clicks and
types into the frontmost window, so it can't run while you work, and every
observation is an image. offstage inverts both: background-only channels, and
text observation with pixels reserved for the checks that need them.

Measured, seeded-defect benchmarks (single host, macOS 26.1):

| claim                         | number                                                                                                           |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| equal or better defect recall | blind agents on text vs screenshots: 5/6 vs 5/6 (frontier model), 4/6 vs 3/6 (small), 6/8 vs 5/8 (second app)    |
| far cheaper observation       | 3.6–28× fewer observation tokens; 19–31% cheaper whole-session                                                   |
| smaller models degrade less   | small model lost 2/6 recall on screenshots, 1/6 on text                                                          |
| free regression mode          | scripted batteries: 13/13 and 8/8 seeded defects, 0 false alarms in 57 clean probe outcomes, ~30 s/run, 0 tokens |
| fast channels                 | AX read p50 8 ms · SCK capture p50 41 ms, byte-identical on static scenes · port round-trip p50 0.04 ms          |

The two modes are complementary: pixels miss semantics (label defects aren't
pixels), text misses typography (font regressions need the golden diff). Run
both — offstage exposes both. Details: [docs/channels.md](docs/channels.md).

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

## Quick start

```sh
pip install -e .
offstage probes build       # compile the Swift probe binaries (one-time)
offstage doctor             # check session, permissions, toolchain
```

Try the bundled fixture app:

```sh
cd examples/NotesApp
xcodegen generate
xcodebuild -project NotesApp.xcodeproj -scheme NotesApp -configuration Debug \
  -derivedDataPath /tmp/offstage-nb-dd build
cd ..

offstage start notesapp.manifest.json
offstage press notesapp.manifest.json addNote
offstage observe notesapp.manifest.json
offstage port notesapp.manifest.json '{"cmd":"rename","index":0,"title":"Hello"}'
offstage golden bake notesapp.manifest.json   # goldens are per-machine
offstage golden check notesapp.manifest.json
offstage stop notesapp.manifest.json
```

For your own app: write a manifest ([docs/manifest.md](docs/manifest.md)) and
embed the port ([swift/OffstagePort](swift/OffstagePort)).

## Use with Claude Code / Codex / other agents

The CLI is the agent interface — any agent that can run shell commands can QA
an app with it. A ready-made skill teaches the workflow and the safety rules:

```sh
offstage skill install                 # copies into ~/.claude/skills
offstage skill install --target .agents/skills   # or anywhere else
```

Claude Code can also install it as a plugin:

```
/plugin marketplace add <github-user>/offstage
/plugin install offstage-qa@offstage
```

For agents without a skill mechanism, paste the contents of
[skills/offstage-qa/SKILL.md](skills/offstage-qa/SKILL.md) into your
`AGENTS.md`.

## Deterministic batteries

[bench/](bench/) holds scripted probe batteries for the fixture apps: launch,
a11y scan, journeys, edge inputs, persistence, canonical goldens, and an
app-never-frontmost safety check. They are the integration tests, and the
template for turning your own app's journeys into a ~30 s, zero-token
regression gate:

```sh
python3 bench/battery_notes.py baseline --make-golden
python3 bench/battery_notes.py check
```

## Host requirements

- macOS 15+ (measured on 26.1), Xcode command-line tools; `xcodegen` for the
  example apps.
- Unlocked screen, display awake (`caffeinate -du` for long runs). The driver
  refuses to run into a locked session — channels degrade silently.
- Accessibility + Screen Recording permission for the host terminal. One-time
  manual grants; no programmatic way around them, including in CI.

## Limits

No synthetic input on a shared desktop. No background typing into SwiftUI
fields (AX set-value looks like it works; the store never changes). Goldens
are byte-exact same-machine only. Full list, with the failures behind each
rule: [docs/limits.md](docs/limits.md).

## Repo layout

| path                   | what                                                        |
| ---------------------- | ----------------------------------------------------------- |
| `src/offstage/`        | Python driver + CLI (`offstage`), manifest validator        |
| `src/offstage/probes/` | single-file Swift probes (AX, SCK, pixdiff, session lock)   |
| `swift/OffstagePort/`  | Swift package: the semantic port apps embed in debug builds |
| `skills/`              | agent skill (Claude Code plugin layout)                     |
| `examples/`            | two fixture apps (NotesApp, ConvertApp) + manifests         |
| `bench/`               | deterministic probe batteries (= integration tests)         |
| `docs/`                | channel table, limits, manifest reference                   |

## Provenance

Extracted from a private research program on agentic macOS QA — channel
measurement, perception ablations, seeded-defect benchmarks. Where a rule
looks oddly specific, violating it broke a run.

## License

MIT — see [LICENSE](LICENSE).
