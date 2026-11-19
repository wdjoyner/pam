# PAM tests

Regression tests for the baseline of *PAM: The Road to Blender*, Milestone 1.
None of them writes a video, and none writes into the repository.

```bash
python -m pytest             # all tests (about a minute and a half)
python -m pytest -k golden   # golden-trace comparison only
python -m pytest -k validate # validator only (a few seconds)
```

Needs `pytest` and a working PAM install (Manim). Two groups of tests need
something extra and are skipped without it:

| Tests | Need |
|---|---|
| `test_fountain2pam_warnings.py` | `screenplain` (as `fountain2pam.py` does) |
| `test_blender_build.py` | Blender: `pip install bpy`, or a `blender` program on `PATH`, or `BLENDER=/path/to/blender` |

## What is covered

| File | What it checks |
|---|---|
| `test_golden_traces.py` | A fresh `pam_trace.py` trace of each fixture matches the stored one within 0.002. One comparison covers scaling, locomotion, poses, prop attachment and handoff, camera moves, and speech bubbles. |
| `test_blender_build.py` | `trace2blender.py` builds a `.blend` from a stored golden trace without error. |
| `test_validate.py` | The JSON validator and the `pam-validate` command, including what they report for each fixture. |
| `test_action_specs.py` | `pam/action_specs.py` lists exactly the actions `pam_player.py` dispatches. |
| `test_fountain2pam_warnings.py` | `fountain2pam.py --warnings-json`, and that the validator reports the same `# REVIEW` comments. |
| `test_dry_run_updaters.py` | Manim advances updaters on every frame in dry-run mode (see below). |
| `test_version_label.py` | `pam.__version__` and the module docstrings agree. |

## Fixtures and golden traces

The fixtures are three screenplays in the repository root:

- `screenplay_alice-meets-bob.json`
- `lucy-meets-lenny2_pam.json`
- `wdj_nona-vs-governor-venus3.json`

Their traces are stored in `tests/golden/`. `tests/golden/BASELINE.json` records
the reference commit (`8af434d`, the code the baseline protects), the PAM
version label at that commit, the tolerance, and the recording environment
(Python, Manim, platform). Each fixture also has a `recorded_at` entry; the
`lucy-meets-lenny2_pam.json` trace was recorded again after that fixture was
corrected.

### When a golden test fails

The failure lists the values that differ, by their path in the trace, for example
`tracks.lenny[3].to.head[0]: golden 4.5003, fresh 4.5028`.

- If you did not mean to change how PAM moves or times things, the change you
  made has a side effect. That is what the test is for.
- If the change is intended, record new golden traces and commit them with a
  note on why they changed:

  ```bash
  python tests/update_golden.py                              # all three
  python tests/update_golden.py lucy-meets-lenny2_pam.json   # just one
  git diff --stat tests/golden
  ```

Editing a fixture screenplay also requires recording its trace again; a test
says so if you forget.

### Strict and portable comparison

PAM draws text in "Courier New". A machine without that font substitutes
another, so speech-bubble sizes and glyph outlines differ from machine to
machine even when the performance is identical. The tests therefore measure
one line of text first:

- **strict**: the measurement matches `BASELINE.json`; every value is compared.
- **portable**: it does not match; the font-dependent values (bubble size,
  position and tail, card and prop outlines) are skipped, with a warning.
  Joint motion, timing, camera, props, visibility, and actions are still
  compared.

The stored traces were recorded on Linux, where Liberation Mono stands in for
Courier New. On a Mac with the real font, expect the portable comparison. To
get the strict comparison on your own machine, first check that the portable
comparison passes, then run `python tests/update_golden.py` there and commit
the result. `PAM_GOLDEN_MODE=strict` or `PAM_GOLDEN_MODE=portable` forces a
mode.

## Findings recorded while building the baseline

**Updaters in dry-run mode (Milestone 1, task 7).** Manim does advance
updaters on every frame in the dry-run mode the tracer uses: with Manim 0.22.1
(Cairo renderer) a dry run calls each updater at exactly the same times and
with the same `dt` as a render that writes video. So the tracer does not need
to step constraints itself. One thing to plan for in Milestone 3: the tracer
looks at the scene only before and after each `play`, so it does not yet *see*
the frames in between. Recording a `sampled` piece needs a per-frame sampler,
and an updater is a workable place for one.

**The fixtures themselves.** `pam-validate` finds no errors in the three
fixtures. `lucy-meets-lenny2_pam.json` originally had two dead steps left by
the compiler: `trot_to` aimed at `lucy` (a human) and at `ramis` (a name that
is never spawned; the dog prop is called `dog`). The player skipped both with
a "not a DogGraph" message. The fixture now spawns the dog first and has it
trot to center stage, and its golden trace was recorded again. Today's
`fountain2pam.py` still produces those two steps from the `.fountain` source
(its "trots/jogs" rule uses the speaker's name where the `dog` prop key
belongs), so compiling that file again brings them back.

**The patch guide.** `fountain2pam.py` prints "(Hints also written as
_comment entries at bottom of JSON.)", but it appends the hints after the
JSON file has been written, so they are not in the file. The compiler's
output is unchanged here; `--warnings-json` captures the hints.
