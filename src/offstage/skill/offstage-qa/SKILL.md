---
name: offstage-qa
description: QA a macOS app in the background while the user keeps using their Mac, via the offstage harness (AX perception, semantic port, canonical pixel goldens, ground-truth verification). Use when asked to test, QA, exercise, or regression-check a native macOS app; when verifying a macOS app change works in the real app; or when the user mentions offstage, a manifest, goldens, or background app testing.
---

# QA a macOS app with offstage

offstage drives a macOS app **in the background**: the app never becomes
frontmost, and no synthetic input ever reaches the user's foreground. You
perceive through the accessibility tree, act through `AXPress` and a semantic
port, and verify against ground truth, not screenshots.

## Prerequisites (check once per session)

```sh
offstage doctor
```

If `offstage` is not installed: `pip install offstage` (or `pip install -e '.[dev]'`
inside the harness repo). Doctor failing on a locked screen or missing
Accessibility or Screen Recording permission is a **user action**: report it
and stop; there is no programmatic workaround.

The app under test needs a manifest (JSON describing bundle id, app path,
socket, goldens). Look for `*.manifest.json` in the repo; if none exists,
create one from the reference in the harness docs (`docs/manifest.md`) and
validate it:

```sh
offstage validate <app>.manifest.json
```

## The verbs

```sh
offstage start <manifest>          # launch fresh (full state reset)
offstage restart <manifest>        # relaunch WITHOUT reset (persistence check)
offstage stop <manifest>
offstage press <manifest> <ax-identifier>
offstage menu <manifest> <menu-title> <item-title>
offstage port <manifest> '<json>'  # semantic action; app-specific commands
offstage observe <manifest>        # compact JSON: AX rows, defaults, port state, a11y counts
offstage golden check <manifest>   # canonical-state pixel diff (resets app state!)
offstage golden bake <manifest>    # rewrite goldens (only when a visual change is intended)
offstage batch <manifest> <steps>  # a whole step list in one call (see below)
```

## Run journeys with `batch`, not verb-by-verb

One CLI call costs you a turn, so a ten-step journey costs ten. `batch` runs
the list in one process and returns one JSON result. Steps are the same verbs
plus `expect <json-pointer> <expected-json>`, which asserts against ground
truth and makes the batch self-judging.

```sh
offstage batch app.manifest.json '[
  ["start"],
  ["press","addNote"],
  ["expect","/defaults/notes.v1/0/title","\"Untitled\""],
  ["port","{\"cmd\":\"rename\",\"index\":0,\"title\":\"TOP\"}"],
  ["expect","/port/titles","[\"TOP\"]"]]'
```

Steps can also be a `.json` file path or `-` for stdin. The pointer resolves
against `{"defaults": <persisted store>, "port": <the port's state reply>}`;
dotted keys like `notes.v1` are ordinary pointer tokens. Exit status is 1 when
any step fails, and the result names the failing step with `want`/`got`. The
run stops at the first failure (`--keep-going` overrides) and always stops if
the app dies.

Reach for single verbs when exploring — one press, then `observe` to see what
the app did. Once you know the journey, batch it.

## Working discipline

- **Observe with `observe`, never screenshots.** It returns AX structure,
  persisted store (ground truth), port state, and a11y counts in one compact
  JSON, at about 1/20th the tokens of an image, and more reliable.
- **Verify against ground truth.** A defect claim must cite the `defaults`
  or port-state evidence, not just an action's echo. After every mutating
  action, check `app_alive=` in the output. A dead app is a crash finding.
- **Typing, tab switching, and drags go through `port`.** Background AX
  cannot type into SwiftUI fields or switch TabView tabs. An unswitchable
  tab is a harness limit, NOT an app defect. The port's commands are
  app-specific; discover them in the app's `PortSetup.swift` (or equivalent
  AgentPort handler).
- **`golden check` resets the app** to its canonical fixture state before
  capturing. Run it last, and expect previous session state to be gone.
  Diff above the manifest threshold (default 0.1%) = real visual change.
  Never `golden bake` to make a failure pass; bake only when the user
  intended a visual change.
- **Persistence checks**: set distinctive state, `restart` (not `start`),
  confirm the state survived.

## Safety rules (hard)

- Never inject synthetic keyboard/mouse events (no `cliclick`, no
  osascript keystrokes, no CGEvent tools). offstage's channels are the only
  approved actuation.
- If any command reports the session is locked, stop and tell the user.
- Report findings with evidence (probe output, diff percentages); never
  claim a pass without the command output showing it.

## Crystallize when done

When a QA pass finds journeys worth keeping, save the step lists as `.json`
files and re-run them with `batch` — each one already carries its own
`expect` assertions, so it re-runs at zero model tokens. For journeys that
need logic a step list cannot express (state repair, conditionals), encode a
battery script instead (see `bench/battery_notes.py` in the harness repo for
the template).
