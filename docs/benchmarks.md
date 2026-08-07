# Measured numbers

Every claim offstage makes, with the measurement behind it. Single host,
macOS 26.1, n=20 per channel unless noted. Channel latencies and the
perception ablations come from the research program this harness was
extracted from; the runtime numbers come from the current driver.

## Channel latency

| channel                           | measured                                                    |
| --------------------------------- | ----------------------------------------------------------- |
| AX tree read (`axdump`, `axscan`) | attach + full read p50 8 ms; pruned-tree diff ~21 tokens    |
| ScreenCaptureKit window capture   | p50 41 ms, works occluded, 20/20 byte-identical when static |
| semantic port round-trip          | p50 0.04 ms                                                 |
| action to AX-tree-settled         | p50 38 ms, p95 56 ms                                        |

## Text perception beats screenshots

Blind agents ran the same seeded-defect apps twice: once observing the AX
tree plus ground truth, once observing screenshots.

| measure                      | result                                                                |
| ---------------------------- | --------------------------------------------------------------------- |
| defect recall, frontier      | text 5/6, screenshots 5/6                                             |
| defect recall, small model   | text 4/6, screenshots 3/6                                             |
| defect recall, second app    | text 6/8, screenshots 5/8                                             |
| observation tokens           | text 3.6x to 28x cheaper                                              |
| whole-session cost           | text 19% to 31% cheaper; orchestration dominates outside observations |
| degradation as models shrink | the small model lost 2/6 recall on screenshots, 1/6 on text           |

Neither mode is complete on its own. Pixels miss semantics, because an
accessibility-label defect is not a pixel. Text misses typography, because a
font regression only shows in the golden diff. Run both.

## Deterministic batteries find defects for free

Scripted probe batteries, no model in the loop:

- 13/13 seeded defects caught in the notes app, 8/8 in the converter.
- 0 false alarms across 57 clean probe outcomes.
- ~9 s per run (notes), ~6 s (converter). 0 model tokens.
- One class needs them: order-sensitive defects, like a stale recompute after
  a specific journey order. Both blind-agent arms missed one the battery
  catches explicitly.

Reproduce with `python3 bench/battery_notes.py check` (bake goldens locally
first; see [bench/README.md](../bench/README.md)).

## Batching a journey costs one turn instead of twelve

The same ten-step NotesApp journey, run verb by verb versus as one `batch`
call. Per-verb verification means an `observe` dump after every mutation;
`batch` asserts with `expect` and answers in a few bytes.

| flow     | agent turns | observation tokens | wall clock |
| -------- | ----------- | ------------------ | ---------- |
| per verb | 12          | ~2000              | 2.4 s      |
| `batch`  | 1           | ~340               | 1.15 s     |

Turns are the win worth having. Wall clock was already small.
Reproduce with `python3 bench/bench_batch.py 3`.

## Settling on a barrier, not a sleep

The driver used to sleep 0.6 s after every action and 0.8 s after launch.
Actions settle in 38 ms p50, so the sleep spent an order of magnitude more
than the work needed and still only guessed. It now settles on an
`offstage.ping` port round-trip, whose reply crosses `DispatchQueue.main.sync`
and therefore proves the action's main-thread work has run.

| notes battery        | median run | clean runs |
| -------------------- | ---------- | ---------- |
| flat sleeps          | 19.9 s     | 1/3        |
| ping barrier         | 9.0 s      | 11/13      |
| barrier + press poll | 9.0 s      | 12/12      |

Removing the sleeps exposed a second race they had been covering. The main
thread finishing is not the AX tree updating: a control that an action just
revealed can be missing from the tree for tens of ms, and `axpress` used to
give up on the first look. It now polls to a 1.5 s deadline, so a missing
target is only reported once it stays missing. That took the residual
`journey-delete-undo` flake (2 failures in 13 runs) to 0 in 12.
