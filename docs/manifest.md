# Manifest reference

All per-app knowledge lives in a manifest JSON — data, not code. The harness
verbs are generic. Validate with `offstage validate <manifest>`.

```json
{
  "name": "NotesApp",
  "bundle_id": "com.example.offstage.NotesApp",
  "app_path": "/tmp/offstage-nb-dd/Build/Products/Debug/NotesApp.app",
  "sock_path": "/tmp/offstage-nb.sock",
  "launch_args": [],
  "canonical_fixture": [
    ["press", "addNote"],
    ["port", "{\"cmd\":\"rename\",\"index\":0,\"title\":\"GOLD-A\"}"]
  ],
  "goldens": [
    { "name": "wide", "size": "1000x600", "file": "NotesApp/goldens/wide.png" }
  ],
  "golden_threshold_pct": 0.1,
  "a11y_baseline": { "unlabelled_buttons": 3, "empty_menu_items": 27 }
}
```

| field                  | required | meaning                                                                                                  |
| ---------------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `name`                 | yes      | process name (used for pgrep and crash-residue cleanup)                                                  |
| `bundle_id`            | yes      | CFBundleIdentifier (AX attach, `defaults export`, appearance pinning)                                    |
| `app_path`             | yes      | built .app to launch                                                                                     |
| `sock_path`            | yes      | UNIX socket for the semantic port; keep it short (`sun_path` caps ~104 bytes)                            |
| `launch_args`          | no       | extra `--args` passed at launch                                                                          |
| `canonical_fixture`    | no       | driver steps that rebuild the exact state goldens are baked from (`press`/`menu`/`port`/`sleep`)         |
| `goldens`              | no       | window sizes + files for canonical-state pixel goldens                                                   |
| `golden_threshold_pct` | no       | diff % above which a golden check fails (default 0.1; values inside the ~0.08% noise band are rejected)  |
| `a11y_baseline`        | no       | expected `axscan` counts; batteries compare against it (host/OS-version specific — re-baseline per host) |

Relative paths resolve against the manifest file's directory.

## Requirements on the app under test

- Honor the port flag: start an OffstagePort (debug builds only). Use
  `AgentPort.fromLaunchArguments` — the driver passes `-uitest-port <sock>`
  (a `-key value` pair, which AppKit strips; bare `--flags` become "documents
  to open" and suppress window creation once three accumulate — see
  [limits.md](limits.md)); `--uitest-port <sock>` also works for manual runs.
- Honor the reset flag (`AgentPort.resetRequested`): drop the persistent
  domain and start as a fresh user (also clears NSWindow frame / NSSplitView
  autosave — layout leaks across runs otherwise and breaks goldens).
- Give interactive elements `.accessibilityIdentifier`s: they are how `press`
  targets controls and how findings are pinned to elements.
