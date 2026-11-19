# PAM tests

Regression tests for *PAM: The Road to Blender*: the Milestone 1 baseline,
the vertical slice, the Milestone 2 timeline, and the Milestone 3 constraints
and choreography routines.
None of them writes a video, and none writes into the repository.

```bash
python -m pytest             # all tests (about four minutes)
python -m pytest -k choreography  # Milestone 3, with its completion test
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
| `test_blender_build.py` | `trace2blender.py` builds a `.blend` from a stored golden trace without error; in the built scene a constrained hand stays on the wrist it holds, including a wrist that moves, and the contacts of the Scene 2 routines hold (the pull, the offered hand, the pop). |
| `test_blender_mouth.py` | Talking mouths in the Blender export: shown only while the character's bubble is showing, kept with `--no-bubbles`, removed by `--no-mouths`. |
| `test_timeline.py` | The 15 fps frame clock: a duration in `frames` lasts exactly that many frames, sequences and beats land on their frames, and legacy screenplays are not touched. |
| `test_timeline_blocks.py` | Timed `parallel` blocks (Milestone 2): overlapping moves start and end on their frames and keep their easing, a line of dialogue and a camera cut land on their frames, walks take exactly their frames, constraints start and end inside a block, repeated runs are identical, a block is exact at 30 fps, and ordinary `parallel` blocks and `say` lines are not touched. |
| `test_constraints.py` | The two-bone solver, `joint_to_joint` and `root_lock`, release on a set frame, the fall and the comic hold, the `sampled` trace piece, and the same gag at other character scales. |
| `test_choreography.py` | Milestone 3. `joint_to_point` and `joint_to_prop` (a hand on a point, a foot planted, a hand that follows a moving prop, a hand on a wrist that is itself held). How a routine's `frames` are shared over its phases. The Scene 2 routines `pull_immovable`, `cork_pop_up` and `mismatched_hug`: phases on their frames, a routine as a step of a timed block, and what each gag must show. The roadmap's completion test (below). |
| `test_validate.py` | The JSON validator and the `pam-validate` command, including what they report for each fixture. |
| `test_action_specs.py` | `pam/action_specs.py` lists exactly the actions `pam_player.py` dispatches. |
| `test_fountain2pam_warnings.py` | `fountain2pam.py --warnings-json`, and that the validator reports the same `# REVIEW` comments. |
| `test_dry_run_updaters.py` | Manim advances updaters on every frame in dry-run mode (see below). |
| `test_version_label.py` | `pam.__version__` and the module docstrings agree. |

## Fixtures and golden traces

The fixtures are six screenplays in the repository root:

- `screenplay_alice-meets-bob.json`
- `lucy-meets-lenny2_pam.json`
- `wdj_nona-vs-governor-venus3.json`
- `abe-isaac_wrist-pull_slice.json` (the vertical slice: timeline, contact
  constraint, sampled trace piece; trace version 5)
- `abe-isaac_overlap_timeline.json` (Milestone 2: one timed parallel block
  with a walk, overlapping moves, two lines of dialogue, two camera moves,
  and a grip that starts and ends inside the block)
- `abe-isaac_scene2-gags.json` (Milestone 3: `pull_immovable`, `slip_on_back`,
  `cork_pop_up` and `mismatched_hug`; the last two run inside timed parallel
  blocks, under dialogue and camera cuts)

The first three predate the timeline. They are the proof that it is opt-in:
they must keep tracing as version 4 and keep matching their golden traces.

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
  python tests/update_golden.py                              # all of them
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

## The Milestone 3 completion test

The roadmap's test for Milestone 3 reads: *change Isaac's scale from 1.15 to
1.30 and replay the Scene 2 physical gags; the movements remain coherent
without manual re-blocking, and no elbow or knee flips direction.* It is
`test_gags_survive_isaac_at_1_30` in `test_choreography.py`.

The fixture's Isaac is 0.80 tall and 0.92 wide, which is 1.15 times 0.80, next
to an Abraham of 0.48. The test traces `abe-isaac_scene2-gags.json` again with
only Isaac's `scale` changed, in two readings of "1.15 to 1.30":

- **wider**: his width factor goes from 1.15 to 1.30 (0.92 to 1.04);
- **larger**: all of him grows by 1.30/1.15 (0.80 by 0.92 to 0.904 by 1.04).

For each it checks:

- **no re-blocking**: every beat and every block is on the frame it was on;
- **the pull reads**: Abraham's hand is on Isaac's wrist from the end of the
  reach to the release, Isaac's joints do not move, Abraham's shoulder goes
  back and down until the arm is taut, the arm slackens and snaps taut in the
  heaves, and his feet stay on the ground;
- **the slip reads**: he ends flat, on the ground, head away from Isaac;
- **the cork-pop reads**: Isaac's hand gets down to the offered point, the two
  hands stay together through the pop, Abraham leaves the ground by the
  routine's hop and ends upright on it, beside Isaac and not inside him, and
  Isaac is back exactly where he started;
- **the hug reads**: Abraham stands against Isaac's near side, both arms go
  across Isaac, an arm that cannot reach is straight, and the reported
  shortfall is the measured one;
- **nothing flips**: on every constrained limb the elbow or knee stays on one
  side for the life of the constraint, the side a bent limb was already on;
  and no elbow or knee of either figure jumps from one side to the other
  between two frames of a routine.

A third test sets Isaac's scale to 1.30 outright (more than two and a half
times Abraham). That is outside the character design, and the routines
re-block: Abraham pulls Isaac by the knee and hugs his leg. Two more run the
scene mirrored, and with an Isaac small enough that the hug reaches around.

"Reads" here means these measurable properties. Whether a gag is funny at a
given size is still a judgment for someone watching the render.

## Findings recorded while building the baseline

**Updaters in dry-run mode (Milestone 1, task 7).** Manim does advance
updaters on every frame in the dry-run mode the tracer uses: with Manim 0.22.1
(Cairo renderer) a dry run calls each updater at exactly the same times and
with the same `dt` as a render that writes video. So the tracer does not need
to step constraints itself. One thing to plan for in Milestone 3: the tracer
looks at the scene only before and after each `play`, so it does not yet *see*
the frames in between. Recording a `sampled` piece needs a per-frame sampler,
and an updater is a workable place for one.

**A frame listener that outlives its block (found in Milestone 3, not
changed).** `pam.timeline.Block.run` adds a scene updater while a tracer is
listening and removes it with `scene.remove_updater(self._tick)`. Manim removes
updaters by identity, and `self._tick` is a new bound-method object each time it
is written, so the updater stays. After the first timed block of a scene the
tracer therefore goes on recording frame by frame to the end of the scene.
The positions are right (it is what Manim drew), and ordinary renders are not
affected, because the updater is only added while tracing. The cost is a larger
trace, and moves after the block lose their pose names and easing in it. The
fix is to keep the bound method in a variable and use it for both calls. It
has not been made here because it changes one number in a golden trace
(`stats.plays` of `abe-isaac_overlap_timeline.json`, 96 to 90: the frames of the
closing wait are no longer counted one by one), and the goldens were to stay
as they are. Making it means recording that trace and
`abe-isaac_scene2-gags.json` again.

**The fixtures themselves.** `pam-validate` finds no errors in the three
fixtures. `lucy-meets-lenny2_pam.json` originally had two dead steps left by
the compiler: `trot_to` aimed at `lucy` (a human) and at `ramis` (a name that
is never spawned; the dog prop is called `dog`). The player skipped both with
a "not a DogGraph" message. The fixture now spawns the dog first and has it
trot to center stage, and its golden trace was recorded again. The cause was
in `fountain2pam.py`: its "trots/jogs" rule used the character's name where
the `dog` prop key belongs, and applied to humans too. The rule now addresses
a dog by its prop key, spawns the dog before its first trot, and leaves a
human who jogs to the humanoid rules (which emit `run_to`). Of the four
`.fountain` files in the repository only `lucy-meets-lenny2_pam.fountain`
compiles differently.

**Every screenplay in the repository validates.** `test_validate.py` checks
all the `.json` screenplays in the repository root, not only the fixtures.
In `tntd_screenplay+sound_2026-07-12.json` this meant three corrections:
26 `pause` steps (not an action, so the pauses never happened) became `wait`;
`set_uniform` became `change_uniform`; and a `move_prop` that named
`athena_seat` now moves `seat_athena`.

**The patch guide.** `fountain2pam.py` prints "(Hints also written as
_comment entries at bottom of JSON.)", but it appends the hints after the
JSON file has been written, so they are not in the file. The compiler's
output is unchanged here; `--warnings-json` captures the hints.

**Frame counts in Manim (vertical slice).** Manim renders
`len(numpy.arange(0, run_time, 1/fps))` frames for a play, and for some whole
numbers of frames the plain quotient is a hair too large: 23/15 and 31/15
seconds render 24 and 32 frames. A wait during which nothing can change is
counted differently again (`int(run_time * fps)` copies of one frozen frame).
`pam/timeline.py` therefore passes `n/15` seconds less one nanosecond, and the
player steps a wait given in frames frame by frame. `test_timeline.py` checks
every count from 1 to 45.

**Two tracer fixes found on the way.** `Scene.wait` plays through `Scene.play`,
and the tracer wraps both, so a change during a wait was recorded twice; the
duplicate is now dropped. Overlay ids for gloves and shoes were handed out in
set order, which varies from run to run, so two traces of the same scene could
differ; the order is now sorted. Neither changes the three legacy golden
traces.

**Timed blocks (Milestone 2).** Four things turned up while building them.

- *Mobjects can only come and go between plays.* Manim decides at the start
  of a `Scene.play` which mobjects it redraws, so a bubble that fades in
  halfway through a play is not drawn. A timed block is therefore cut at
  every frame on which a step starts or ends, and each stretch is its own
  play. An empty mobject at the back of the scene makes Manim redraw
  everything during the block.
- *Finishing an animation undoes a contact for an instant.* When a step ends,
  its animation puts the joints on the pose's targets, including a wrist that
  a constraint was holding. Nothing is drawn in that state, but the tracer
  saw it and recorded a jump (0.6 units, visible in Blender). The block now
  runs the updaters again after finishing steps, as `Scene.play` does.
- *A fade-out needs its group in the scene.* `Scene.play` adds an animated
  mobject that is not in the scene as itself (a figure's edge group; its lines
  are) before it begins, and `FadeOut` relies on that to remove it at the end.
  The block does the same.
- *One frame is exactly 1/15 s.* For a single frame the nanosecond that
  `frames_to_seconds` subtracts makes Manim warn that the play is too short
  (and then use 1/15 s anyway). One frame is now passed as exactly 1/15 s,
  which is exact at 15, 30 and 60 fps.

The tracer records a timed block frame by frame (one linear piece per frame
for whatever moved), since a play there is a stretch of several moves and has
no single rate function. `seconds_to_frames` now rounds halves up (0.3 s is 5
frames); Python's own rounding would give 4 for 0.3 s and 8 for 0.5 s.

**The camera mode switch.** `PAM_CAMERA_MODE=0` does not turn camera mode
off: the player tests `bool(os.environ.get("PAM_CAMERA_MODE", "1"))`, and the
string `"0"` is true. Only an empty value turns it off. This is left as it
is here, because changing it would change how existing command lines render.

**What the Blender check does and does not show.** The tests measure, inside
the built `.blend`, the distance between the constrained hand and the wrist on
every frame: zero for the wrist-pull, under 0.002 on keyed frames and under
0.01 between them when the wrist itself moves. They do not judge how the scene
looks.
