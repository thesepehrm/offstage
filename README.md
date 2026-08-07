# offstage

**Background QA for macOS apps while you keep using your Mac.**

An AI agent (or a plain script) drives and verifies a native macOS app that
never comes to the foreground. No synthetic input reaches whatever you're
typing into.

```
┌────────────┐   press / menu (AXPress)   ┌──────────────────┐
│  offstage  │ ─────────────────────────▶ │  app under test  │
│   driver   │   port (line-JSON/UNIX)    │   (background,   │
│            │ ─────────────────────────▶ │  never frontmost)│
│            │ ◀───────────────────────── │                  │
└────────────┘   AX tree · SCK pixels ·   └──────────────────┘
                 UserDefaults ground truth
```

## Four channels

| channel          | what the agent gets                                                   |
| ---------------- | --------------------------------------------------------------------- |
| **structure**    | accessibility tree as compact text (`observe`)                        |
| **pixels**       | ScreenCaptureKit captures, canonical-state golden diffs (`golden`)    |
| **control**      | `AXPress` for buttons and menus, a semantic port for typing and drags |
| **ground truth** | the app's persisted state, so verification never trusts the UI        |

The one refusal: no synthetic keyboard or mouse events. Those land in
whatever window is frontmost, including yours. What each channel can and
can't do: [docs/channels.md](docs/channels.md).

## Why not a computer-use agent

A screenshot-driven agent needs the foreground, so it can't run while you
work, and every observation costs an image.

Measured against screenshot-driven runs on seeded-defect apps:

- Equal or better defect recall, at 3.6x to 28x fewer observation tokens.
- Smaller models degrade less on text than on screenshots.
- Scripted batteries catch 13/13 and 8/8 seeded defects in ~9 s, 0 tokens.

Full tables: [docs/benchmarks.md](docs/benchmarks.md).

## Quick start

```sh
pip install -e .
offstage probes build       # compile the Swift probes (one-time)
offstage doctor             # check session, permissions, toolchain
```

Build the bundled fixture app:

```sh
cd examples/NotesApp && xcodegen generate
xcodebuild -project NotesApp.xcodeproj -scheme NotesApp -configuration Debug \
  -derivedDataPath /tmp/offstage-nb-dd build
cd ..
```

Drive it:

```sh
offstage start notesapp.manifest.json
offstage press notesapp.manifest.json addNote
offstage observe notesapp.manifest.json
offstage golden bake notesapp.manifest.json    # goldens are per-machine
offstage stop notesapp.manifest.json
```

## The verbs

| verb                           | does                                              |
| ------------------------------ | ------------------------------------------------- |
| `start` / `restart` / `stop`   | launch fresh, relaunch without reset, quit        |
| `press <id>` / `menu <m> <i>`  | AXPress a button or menu item                     |
| `port '<json>'`                | semantic action: typing, tabs, drags              |
| `observe`                      | AX rows, persisted state, port state, a11y counts |
| `golden check` / `golden bake` | canonical-state pixel diff, or rewrite goldens    |
| `batch <steps>`                | a whole journey in one call (below)               |

## Run journeys with `batch`

One CLI call costs an agent one turn, so a ten-step journey costs ten.
`batch` runs the list in one process and returns one JSON result.

```sh
offstage batch notesapp.manifest.json '[
  ["start"],
  ["press","addNote"],
  ["expect","/defaults/notes.v1/0/title","\"Untitled\""],
  ["port","{\"cmd\":\"rename\",\"index\":0,\"title\":\"TOP\"}"],
  ["expect","/port/titles","[\"TOP\"]"]]'
```

`expect` takes an RFC 6901 pointer into `{defaults: the persisted store,
port: the port's state reply}`. It reads ground truth, not the actuation
echo, so the result is pass/fail instead of a dump to interpret.

Steps can also be a `.json` file or `-` for stdin. Exit status is 1 when a
step fails. Batching that journey: 1 turn instead of 12, ~340 tokens instead
of ~2000.

## Use with Claude Code, Codex, and other agents

The CLI is the agent interface. A ready-made skill teaches the workflow and
the safety rules:

```sh
offstage skill install                           # into ~/.claude/skills
offstage skill install --target .agents/skills   # or anywhere else
```

Claude Code can install it as a plugin instead:

```
/plugin marketplace add thesepehrm/offstage
/plugin install offstage-qa@offstage
```

No skill mechanism? Paste
[skills/offstage-qa/SKILL.md](skills/offstage-qa/SKILL.md) into your
`AGENTS.md`.

## Your own app

1. Write a manifest: [docs/manifest.md](docs/manifest.md).
2. Embed the port in debug builds: [swift/OffstagePort](swift/OffstagePort).
3. Crystallize the journeys worth keeping as `batch` step files, or as a
   battery script ([bench/](bench/)) when they need conditionals.

## Host requirements

- macOS 15+ (measured on 26.1), Xcode command-line tools, `xcodegen` for the
  example apps.
- Unlocked screen, display awake. Use `caffeinate -du` for long runs. The
  driver refuses to run into a locked session, because the channels degrade
  silently.
- Accessibility and Screen Recording permission for the host terminal. Both
  are one-time manual grants that nothing can automate, including CI.

## Limits

No synthetic input on a shared desktop. No background typing into SwiftUI
fields, where AX set-value looks like it works but the store never changes.
Goldens are byte-exact on the same machine only.

Full list, with the failure behind each rule:
[docs/limits.md](docs/limits.md).

## Repo layout

| path                   | what                                                        |
| ---------------------- | ----------------------------------------------------------- |
| `src/offstage/`        | Python driver + CLI (`offstage`), manifest validator        |
| `src/offstage/probes/` | single-file Swift probes (AX, SCK, pixdiff, session lock)   |
| `swift/OffstagePort/`  | Swift package: the semantic port apps embed in debug builds |
| `skills/`              | agent skill (Claude Code plugin layout)                     |
| `examples/`            | two fixture apps (NotesApp, ConvertApp) + manifests         |
| `bench/`               | deterministic probe batteries (= integration tests)         |
| `docs/`                | channels, benchmarks, limits, manifest reference            |

## Provenance

Extracted from a private research program on agentic macOS QA: channel
measurement, perception ablations, seeded-defect benchmarks. Where a rule
looks oddly specific, violating it broke a run.

## License

MIT. See [LICENSE](LICENSE).
