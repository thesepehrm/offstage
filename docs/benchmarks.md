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

## A screenshot agent on the same journey

Two notes, two renames, a menu delete, verified at each step. The agent arm
was a real model driving screenshot and click tools, with no offstage access.
The offstage arm was the same journey as one `batch` call.

| arm              | runs | wall clock (median) | turns | tokens | failed |
| ---------------- | ---- | ------------------- | ----- | ------ | ------ |
| screenshot agent | 3    | 44.7 s              | 5     | ~9000  | 1 of 3 |
| offstage battery | 5    | 1.15 s              | 1     | ~300   | 0 of 5 |

39x on the median, and the agent arm never had the machine free: the app was
frontmost the whole time and every keystroke went into it.

Read the failure before the multiple. The failed run deleted both notes
instead of one, because the agent could not tell from pixels that its first
menu click had already landed. It reported success. Reading persisted state
makes that case a mismatch instead of a screenshot that looks fine.

The spread across the three agent runs was 90.6 s, 44.7 s, 32.9 s. The slow
one was the first, before the model had learned that the app's title field
only takes focus when the click lands on the glyphs. Runs 2 and 3 reused that
knowledge, so the median understates a cold agent. Two caveats in the other
direction: n=3 is small, and one delete had to go through the keyboard
shortcut because the sandbox blocked the menu-bar click, which cost the agent
arm two turns.

Reproduce with `python3 bench/bench_agent_vs_battery.py protocol`.

## The same journey as XCUITest

NotesApp ships a `JourneyTests` UI target covering the same ground. Warm
derived data, nothing to compile:

| arm               | wall clock | what you wait for                         | machine    |
| ----------------- | ---------- | ----------------------------------------- | ---------- |
| `xcodebuild test` | 54.5 s     | 41.4 s test phase, 5.5 s per passing case | taken over |
| screenshot agent  | 44.7 s     | model turns                               | taken over |
| offstage `batch`  | 1.15 s     | the app settling                          | yours      |

The per-case time is the fair comparison for the journey itself, and 5.5 s is
still ~5x. The other 49 s is the part you cannot skip: xcodebuild starting,
the runner attaching, the app launching under test.

One of the three cases failed, and the failure is the useful part.
`testJourneyDeleteUndo` could not find the `undoDelete` button: "No matches
found for first query match sequence." At the manifest's window size that
button is not in the tree at all, because SwiftUI collapsed it into an
`AXPopUpButton "more toolbar items"` overflow. One `observe` shows the popup
sitting where the button should be. The XCUITest failure only says the query
matched nothing, and a query that matches nothing looks the same whether the
control moved, was renamed, or was never built.

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
