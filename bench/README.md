# Deterministic probe batteries

Scripted, background-safe, no model in the loop. Each battery drives one
fixture app through the generic driver and writes `bench/data/<app>-<variant>.json`
(one `{probe, pass, detail, ms}` record per probe, plus an
`app-never-frontmost` safety check). Exit code 0 = all probes passed.

These are the harness's integration tests, and the template for
crystallizing your own app's journeys into a sub-10-second, 0-token
regression gate (currently ~9 s for the notes battery, ~6 s for the converter).

```sh
# build the fixture app first (see README quick start), then:
python3 bench/battery_notes.py baseline --make-golden   # first run bakes goldens
python3 bench/battery_notes.py check                    # regression gate
python3 bench/battery_convert.py baseline --make-golden
python3 bench/battery_convert.py check
```

`bench_batch.py` measures what the `batch` verb saves an agent — turns,
observation tokens, and wall clock against the same journey run verb by verb:

```sh
python3 bench/bench_batch.py 3     # median of 3 runs
```

`bench_agent_vs_battery.py` compares offstage against the thing it replaces: a
model driving the same journey through screenshots and synthetic clicks. The
agent arm cannot be scripted, because a model being the loop is what is being
measured, so it is a protocol plus a recorder:

```sh
python3 bench/bench_agent_vs_battery.py offstage 5    # arm A, timed here
python3 bench/bench_agent_vs_battery.py protocol      # arm B, run by hand
python3 bench/bench_agent_vs_battery.py record-agent 44.7 --turns 5
python3 bench/bench_agent_vs_battery.py report
```

The agent arm takes the machine while it runs. That is the measurement, not a
setup problem.

Requirements: unlocked screen, display awake, Accessibility + Screen Recording
permissions for the host terminal. Goldens are byte-exact **same-machine
only**; always bake locally before checking.

Probe classes covered (mirroring the seeded-defect benchmark that validated
this design at 13/13 + 8/8 recall, 0 false alarms): launch, accessibility
hygiene vs baseline, functional journeys, state/flow (persistence, staleness),
crash/hang (edge inputs, port latency), and design (canonical-state goldens at
two window sizes).
