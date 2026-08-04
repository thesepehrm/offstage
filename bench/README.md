# Deterministic probe batteries

Scripted, background-safe, no model in the loop. Each battery drives one
fixture app through the generic driver and writes `bench/data/<app>-<variant>.json`
(one `{probe, pass, detail, ms}` record per probe, plus an
`app-never-frontmost` safety check). Exit code 0 = all probes passed.

These are the harness's integration tests — and the template for
crystallizing your own app's journeys into a ~30 s, 0-token regression gate.

```sh
# build the fixture app first (see README quick start), then:
python3 bench/battery_notes.py baseline --make-golden   # first run bakes goldens
python3 bench/battery_notes.py check                    # regression gate
python3 bench/battery_convert.py baseline --make-golden
python3 bench/battery_convert.py check
```

Requirements: unlocked screen, display awake, Accessibility + Screen Recording
permissions for the host terminal. Goldens are byte-exact **same-machine
only** — always bake locally before checking.

Probe classes covered (mirroring the seeded-defect benchmark that validated
this design at 13/13 + 8/8 recall, 0 false alarms): launch, accessibility
hygiene vs baseline, functional journeys, state/flow (persistence, staleness),
crash/hang (edge inputs, port latency), and design (canonical-state goldens at
two window sizes).
