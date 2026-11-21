# PAM tests

Regression tests for *PAM: The Road to Blender*: the Milestone 1 baseline,
the vertical slice, the Milestone 2 timeline, the Milestone 3 constraints
and choreography routines, Milestone 4 (stateful props and the
continuity ledger, Stage 4a; the scroll, a text-bearing prop, Stage 4b;
the rope, a deformable attachment, Stage 4c), Milestone 5 (Fountain+
choreography cues, projects, and inserts framed from their subject), and
Milestone 6 (the performance of the project's scenes: Scenes 1 and 2,
Stage 6a; Scenes 3 and 4, Stage 6b).
None of them writes a video, and none writes into the repository.

```bash
python -m pytest             # all tests (about five minutes)
python -m pytest -k prop_states   # Milestone 4: the ledger and the knife's
                                  # completion test (no rendering, 3 seconds)
python -m pytest -k scroll        # Stage 4b: the scroll, its text, and its
                                  # completion test (the first file needs
                                  # no renderer and takes a second)
python -m pytest -k rope          # Stage 4c: the rope, its shapes, its
                                  # completion test (test_rope.py needs no
                                  # renderer and takes a second)
python -m pytest -k choreography  # Milestone 3, with its completion test
python -m pytest -k fountain_cues # Milestone 5: cues, the project, and its
                                  # completion test (about a minute)
python -m pytest -k performance   # Milestone 6: acting phases, tics, and
                                  # Scenes 1 to 4 (Stages 6a and 6b; a few
                                  # minutes)
python -m pytest -k performance_6b  # Stage 6b: catch_by_collar, tie_wrist_loop,
                                    # and Scenes 3 and 4 (a few minutes)
python -m pytest -k golden   # golden-trace comparison only
python -m pytest -k validate # validator only (a few seconds)
```

Needs `pytest` and a working PAM install (Manim). Two groups of tests need
something extra and are skipped without it:

| Tests | Need |
|---|---|
| `test_fountain2pam_warnings.py`, `test_fountain_cues.py` | `screenplain` (as `fountain2pam.py` does) |
| `test_blender_build.py` | Blender: `pip install bpy`, or a `blender` program on `PATH`, or `BLENDER=/path/to/blender` |

## What is covered

| File | What it checks |
|---|---|
| `test_golden_traces.py` | A fresh `pam_trace.py` trace of each fixture matches the stored one within 0.002. One comparison covers scaling, locomotion, poses, prop attachment and handoff, camera moves, and speech bubbles. |
| `test_scroll.py` | Milestone 4, Stage 4b, without a renderer. The scroll's machine; writing, crossing out and replacing text, and what an op may not do; text and shape changing independently; text shown letter by letter and a line through a phrase growing from its left end; the validator on scroll steps, also in timed blocks; the ledger carrying the text and its revisions; and the six-scene project, with the completion test for the scroll (below). |
| `test_rope.py` | Milestone 4, Stage 4c, without a renderer. The rope's machine (loose, tied, tightened, snapped; nothing follows a snap); a rope tied only while it is `around` something; attachments to several `joints`, and what an attachment may not say; its two pieces, joined until it snaps and each on its own attachment after; the validator on rope steps, also in timed blocks; the ledger carrying the rope and its pieces; and the six-scene project, with the completion test for the rope (below). |
| `test_rope_shapes.py` | The rope's shapes, plain functions of world positions (`pam.props_carried`): a coil hanging from a shoulder or lying on the ground; a loop that goes round both wrists, stays clear of them, has its knot on top and its break under them, smaller when tight; a piece lying where it fell or hanging from a hand; the throw of a broken end; `attrs.scale`. |
| `test_blender_build.py` | `trace2blender.py` builds a `.blend` from a stored golden trace without error; in the built scene a constrained hand stays on the wrist it holds, including a wrist that moves, and the contacts of the Scene 2 routines hold (the pull, the offered hand, the pop). Stateful props: the knife's handle and blade are built once each and are where the trace has them before and after the break; a hand held on a prop is on it in Blender, also on a prop the builder moves (a door set on the floor); a stateful phone gets its screens. The scroll: its roll, sheet and ribbon each shown in its state, its text letter by letter and the lines through struck text as long as the trace has them, on the same frames, and its grip in Abraham's hand. The rope: each piece built once, as a curve object; its control points in Blender are the trace's, and it is shown when the trace shows it, on every frame of every change and between them; the break of the tied rope is under Isaac's wrists, between them, as Blender places them. |
| `test_blender_mouth.py` | Talking mouths in the Blender export: shown only while the character's bubble is showing, kept with `--no-bubbles`, removed by `--no-mouths`. |
| `test_timeline.py` | The 15 fps frame clock: a duration in `frames` lasts exactly that many frames, sequences and beats land on their frames, and legacy screenplays are not touched. |
| `test_timeline_blocks.py` | Timed `parallel` blocks (Milestone 2): overlapping moves start and end on their frames and keep their easing, a line of dialogue and a camera cut land on their frames, walks take exactly their frames, constraints start and end inside a block, repeated runs are identical, a block is exact at 30 fps, and ordinary `parallel` blocks and `say` lines are not touched. |
| `test_timeline_hardening.py` | The corrections from the referee report on Milestone 2: every overlapping pair of moves of one figure is found and two pose moves at once are an error; a block that would run over is an error; a camera cut in the middle of a walk or a slide frames the drawn figure; a move ending, a move starting, a cut and a release on one frame; the block's frame listener ends with the block; a block that starts off the 15 fps grid at 30 fps. |
| `test_constraints.py` | The two-bone solver, `joint_to_joint` and `root_lock`, release on a set frame, the fall and the comic hold, the `sampled` trace piece, and the same gag at other character scales. |
| `test_choreography.py` | Milestone 3. `joint_to_point` and `joint_to_prop` (a hand on a point, a foot planted, a hand that follows a moving prop, a hand on a wrist that is itself held). How a routine's `frames` are shared over its phases. The Scene 2 routines `pull_immovable`, `cork_pop_up` and `mismatched_hug`: phases on their frames, a routine as a step of a timed block, and what each gag must show. The roadmap's completion test (below). |
| `test_prop_states.py` | Milestone 4, Stage 4a, without a renderer. The prop state machines (the knife, the phone, an item's own, and doors, lids and the Governor as machines of the same kind); what a `prop_transition` may and may not do; the validator on stateful props, also in timed blocks; the continuity ledger file (written, read by the next scene, overrides reported, nothing rewritten when nothing changed); and the six-scene project, with the roadmap's completion test for the knife (below). |
| `test_prop_trace.py` | The same things as the player plays them: prop identities and `prop_state_changed` events in the trace, where every part is on every frame of the knife break, a transition as a step of a timed block, a hand held on a part of the knife, the phone's display changing while the phone stays put (and the reverse), the blade stuck in the altar, the ledger written by playing equal to the one written by validating, and doors, a lid and the Governor through `prop_transition`. The scroll: its text in the trace on every frame of every step that writes or crosses out, exactly as `prop_states.text_row` shows it; its steps in timed blocks; its grip in the hand on every frame, also while Abraham runs; its shape in each state; and in the project, the trace and the ledger agreeing at the end of every scene. The rope: its two pieces and their shapes in the trace, one rope until it snaps, every frame of a change sampled, the coil riding on Abraham's shoulder as he walks, the knot following Isaac's wrists on every frame, pulled tight over its frames, the broken ends springing apart and the pieces lying where the snap puts them; its steps in timed blocks; and in the project, the trace and the ledger agreeing at the end of every scene. |
| `test_fountain_cues.py` | Milestone 5. Beat notes change nothing without a cue file; a cued action or line compiles to a copy of its cue, an empty cue to nothing, an uncued beat as before; the cue report (orphaned cues, beats without cues, duplicates, notes that are not identifiers, cues filed under another scene); malformed cue files; the project's source is the recorded copy of the script, and its scene files are what `fountain2pam.py --project` compiles; no invented cast or props in a project. `pam/shot_targets.py` on its own (the frame for a box, closing in on text, the steps of a shot), the validator on `fit` and `margin`, a fitted cut in a timed block, and an insert without `fit` framed as before. The roadmap's completion test (below). |
| `test_performance.py` | Milestone 6, Stage 6a. The `perform` action: steps placed by acting phase, `until`, a routine's phases given by acting phase, the problems it reports; retiming one phase moves exactly the steps it should and rewrites nothing. `react` with `fragment` (a tic on the frame clock) and `sound_cue` on exact frames; a tic is a pose writer. The acting poses keep the bones and the shoulders of each build and have mirrors facing left. The `barbell` and `magazine` props; the cue file's `scenes.<id>.say`. Traced: a small scene played with two phase tables (the timing changes as expected and a tic returns to its pose), and Scenes 1 and 2 of the project, with the key pose of every gag (below). |
| `test_performance_6b.py` | Milestone 6, Stage 6b. The routines `catch_by_collar` and `tie_wrist_loop`: known to the player, the validator and `perform`; `release: false` and a last phase of 0 frames keep the hold; the catch moves both figures and the tie only the one who ties. The new tic fragments and acting poses (crawling on hands and knees, seated with the feet on the ground, lying back, hanging, the heroic poses). Every cue of Scenes 3 and 4 compiled, the routines on beat notes of action lines, no prose left to stage, no invented dialogue. Traced: the catch and the tie at four combinations of sizes, and Scenes 3 and 4 of the project, with the key pose of every gag (below). |
| `test_validate.py` | The JSON validator and the `pam-validate` command, including what they report for each fixture. |
| `test_action_specs.py` | `pam/action_specs.py` lists exactly the actions `pam_player.py` dispatches. |
| `test_fountain2pam_warnings.py` | `fountain2pam.py --warnings-json`, and that the validator reports the same `# REVIEW` comments. |
| `test_dry_run_updaters.py` | Manim advances updaters on every frame in dry-run mode (see below). |
| `test_version_label.py` | `pam.__version__` and the module docstrings agree. |

## Fixtures and golden traces

The fixtures are eight screenplays in the repository root:

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
- `abe-isaac_knife-break.json` (Milestone 4, Stage 4a: the breakaway knife of
  Scene 2. Abraham draws the knife from his satchel, Isaac takes it by the
  handle with a `joint_to_prop` constraint, the handle comes away and the
  blade drops into the bowl inside a timed parallel block, and Abraham
  gathers the pieces and drops them into the satchel)
- `abe-isaac_scroll-revision.json` (Milestone 4, Stage 4b: the scroll.
  Abraham takes it from his belt, unrolls it, writes the line with a quill
  while he moves, turns its period into a question mark, crosses out THE
  KNIFE? and writes HIS SON. while Isaac says a line, and lets it trail as
  he runs; three of these are steps of timed parallel blocks)
- `abe-isaac_rope-snap.json` (Milestone 4, Stage 4c: the rope. Abraham
  slings the coil over his shoulder and walks with it, winds it round
  Isaac's wrists while Isaac says a line, and yanks the knot tight; it
  follows the wrists as Isaac moves his arms; Isaac flexes and it snaps,
  with two camera cuts, and its pieces recoil and lie on either side of
  the altar. The tie and the snap are steps of timed parallel blocks)

`projects/abe-isaac/` is another kind of fixture: six scenes and a sidecar
with a `continuity` block. The tests always work on a private copy of it,
since validating or playing a scene writes to the ledger. Since Milestone
5 its scene files are compiled from `source/script.fountain` and
`cues/animation_cues.json` (`fountain2pam.py --project`); the Milestone
4 tests run on them as they are.

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

## The Milestone 4 completion test (the knife)

The roadmap's test reads: *every knife component reaches its expected state
and location in every scene, with no disappearing or duplicated pieces; the
ledger tests pass independently of the renderer.* It is
`test_knife_completion` in `test_prop_states.py`, and it imports nothing that
draws.

`projects/abe-isaac/scene1.json` to `scene6.json` are validated in order with
`validate_project` (which is what `pam-validate --project` runs). Each scene
opens from the closing entry the one before wrote. The test then reads the
ledger and compares it with a table taken from Draft 3 of the script
(`writing-guides`, `shorts/abe-and-isaac/script.fountain`):

| Scene | Knife | Handle | Blade | Phone |
|---|---|---|---|---|
| 1 | `intact` | joined; the knife is in the satchel | joined | `standby`, with Isaac, out of sight |
| 2 | `broken` | in the satchel | in the satchel | `standby`, with Isaac, out of sight |
| 3 | `broken` | in the satchel | in the satchel | `standby`, with Isaac, out of sight |
| 4 | `blade_carried` | held by Abraham | in the satchel | `recording`, held by Abraham |
| 5 | `blade_embedded` | held by Abraham | embedded in the altar | `live`, on its rock, 480 viewers |
| 6 | `blade_embedded` | at rest on the ground | embedded in the altar | `live`, held by Isaac, 900 viewers |

For every scene it also checks that the knife has exactly its two parts, each
attached to something, that no second knife or stray part is in the entry,
and that the validator found nothing lost or misplaced.
`test_knife_goes_through_the_script_inside_each_scene` checks every change
between the scene ends (the handle in Isaac's fingers and the blade in the
bowl, before Abraham gathers them). `test_prop_trace.py` then plays the six
scenes: the ledger the player writes is equal to the validator's, no scene's
trace has a piece twice, and each piece is drawn at the end of a scene
exactly when the ledger says it is not hidden.

Three choices in those scenes are blocking decisions, not the script's:
Isaac puts the handle in the bowl before Abraham picks the pieces up; Isaac
pockets his phone as he leaves the cave; and Abraham holds the knife by the
blade, handle toward Isaac.

No scene overrides the ledger, and a test checks that. Building these scenes
showed two places where Draft 3 did not say where the knife was (the pieces
in Abraham's hands at the end of Scene 2 and in a satchel at the start of
Scene 3; both in the satchel at the end of Scene 3 and the blade going *into*
it in Scene 4). The script was edited: Abraham has the satchel from Scene 2
on, draws the knife from it, drops the pieces into it, and in Scene 4 takes
both out before he puts the blade back. The satchel is carried in the ledger
with the knife and the phone.

## The Stage 4b completion test (the scroll)

The task's completion test reads: *without rendering, the scroll has its
expected state, text and location at the end of every scene.* It is
`test_scroll_completion` in `test_scroll.py`, and like the knife's it
imports nothing that draws.

The six scenes are validated in order and the ledger is compared with a
table taken from Draft 3 of the script with the scroll-continuity edits
(writing-guides pull request 10):

| Scene | State | Where | What it says |
|---|---|---|---|
| 1 | `rolled` | in Abraham's belt (right hip) | GENESIS / B'RESHIT; AND ABRAHAM RAISED THE KNIFE? |
| 2 to 5 | `rolled` | in Abraham's belt | the same |
| 6 | `trailing` | held by Abraham (left wrist) | GENESIS / B'RESHIT; AND ABRAHAM RAISED HIS SON. |

It also checks the number of revisions in each scene (two after Scene 1,
three after Scene 6), and that the ledger has exactly one scroll and the
validator found nothing misplaced. Two more tests check the revisions:
each carries the scene it was made in from scene to scene, and every
change inside Scenes 1 and 6 comes in the script's order. The page at the
end still shows the struck words (THE KNIFE, the period, the question
mark) with HIS SON. after them.

Draft 3 did not say what the scroll says or where it is in four places:
whether the question mark replaces the period, where the scroll is from
Scene 1 to Scene 5 (in the satchel or in his hands), that he takes it
from somewhere in Scene 6, and who holds it as it trails. The proposed
script edits (a pull request in `writing-guides`) answer all four, and
the scenes follow them. `test_the_project_needs_the_script_edits` shows
what happens with the other reading of the question mark (`KNIFE.?`):
Scene 6 cannot cross out THE KNIFE?.

One choice is blocking, not the script's: the quill lives in the
satchel (Scene 6 "pulls a quill from the satchel"); Abraham takes it out
to write in Scene 1 and in Scene 6 and puts it back each time.

## The Stage 4c completion test (the rope)

The task's completion test reads: *without rendering, the rope has its
expected state, pieces and location at the end of every scene.* It is
`test_rope_completion` in `test_rope.py`, and like the others it renders
nothing. With the knife's and the scroll's, it completes Milestone 4.

The six scenes are validated in order and the ledger is compared with a
table taken from Draft 3 of the script with the rope-continuity edits
(a pull request in `writing-guides`):

| Scene | State | Pieces | Where |
|---|---|---|---|
| 1 | `loose` | joined | at rest by the cave entrance, out of sight (in the cave) |
| 2 | `loose` | joined | on Abraham (`rshoulder`) |
| 3 | `loose` | joined | on Abraham (`rshoulder`) |
| 4 | `tightened` | joined | around Isaac (`lwrist`, `rwrist`) |
| 5 | `tightened` | joined | around Isaac (`lwrist`, `rwrist`) |
| 6 | `snapped` | apart | `piece_a` at rest left of the altar (x 0.25), `piece_b` at rest right of it (x 2.95), on the ground |

For every scene it also checks that the rope has exactly its two pieces,
joined to it until it snaps, that there is one rope, and that the
validator found nothing lost or misplaced.
`test_the_rope_goes_through_the_script_inside_each_scene` checks every
change between the scene ends, and `test_no_scene_overrides_the_rope`
that no scene departs from the ledger. `test_prop_trace.py` plays the
six scenes and checks that the trace shows the rope where the ledger
says at the end of each.

Draft 3 did not say where the rope was or what became of it in three
places: where it came from (it first appeared in Scene 3, with nothing
in Scene 2), how Abraham carried it in Scene 3 and where it was when he
began to tie Isaac in Scene 4, and where its halves went when it
snapped in Scene 6. The proposed script edits answer all three: a coil
lies by the cave entrance in Scene 2 and Abraham slings it over his
shoulder as he leaves; he carries it there in Scene 3 and takes it from
his shoulder in Scene 4; and its two halves fly off Isaac's wrists and
land in the dirt on either side of the altar. The scenes follow them.
`test_the_project_needs_the_script_edits` shows what happens without
the pickup: the rope is still by the cave entrance in Scene 3.

Two choices are blocking, not the script's: the coil hangs from
Abraham's right shoulder (his satchel is at his left hip), and Isaac
holds out his wrists in the `reach_forward` pose, which Scenes 5 and 6
open in. The roadmap's routine table puts `reach_and_tighten` ("Isaac
accidentally tightens his knot") in Scene 5. That beat is from Draft 2;
in Draft 3 Abraham yanks the knot tight himself in Scene 4 and nothing
happens to the rope in Scene 5, so the scenes follow Draft 3.

## The Milestone 5 completion test

The roadmap's test reads: *recompiling the Fountain screenplay does not
erase hand-authored choreography or incorrectly frame the critical
inserts. Orphaned cues are reported.* It is in `test_fountain_cues.py`,
in three parts, and it renders nothing (the inserts are checked in
traces, a dry run).

**The choreography is kept.**
`test_recompiling_keeps_the_hand_authored_choreography` compiles the
project and finds each of the 42 cues in its scene, verbatim and in one
piece after its `# CUE` comment, and each scene's `before` and `after`
steps at its start and end. `test_rewriting_the_prose_keeps_the_choreography`
rewrites the prose around two beats (and moves one note to its own line)
and recompiles: the steps come out the same. The Milestone 4 tests run
on the compiled scenes: the knife, scroll and rope completion tests
pass, and the ledger the six scenes write is byte for byte the one the
hand-authored scenes wrote (`test_the_ledger_in_the_repository_is_up_to_date`).

**Orphans are reported.** `test_orphaned_cues_are_reported` renames one
beat in the screenplay and deletes the paragraph of another: the
compiler lists the two cues that lost their beats and the beat with no
cue, and `--check` fails. `test_a_cue_for_another_scene_is_reported`
does the same for a cue filed under the wrong scene and a setup for a
scene the project does not have.

**The critical inserts are framed.** Scenes 1, 2, 4, 5 and 6 are traced,
and every insert is a fitted shot:

| Scene | Insert | Framed on | What the test checks |
|---|---|---|---|
| 1 | the scroll, "AND ABRAHAM RAISED THE KNIFE." | its text (5.8% cap height) | all the text in the frame on every frame, filling it from side to side; the line reads as the script says |
| 2 | the knife coming apart in Isaac's hands | the knife (0.55 wide) | the handle in the frame on every frame; the knife whole in the frame at the cut, broken by the end |
| 2 | the blade dropping into the bowl | the bowl, and where the blade lands (0.72 wide) | the bowl in the frame on every frame; the blade lands during the shot and is in the frame from then on; the CAMERA note stands for the cue's cut, not a second one |
| 4 | the phone, a big red LIVE button | the phone (4.1%) | the phone in the frame; its screen shows the record button |
| 5 | the phone going LIVE, the count climbing | the phone, from frame 0 | in the frame; the count reaches 240; the scene opens on it |
| 5 | the count doubling, the comment | the phone on its rock | in the frame; 480 and IS THAT A REAL KNIFE; the legacy insert (7 wide, centered at y = 1.5) would miss it |
| 6 | the scroll, "AND ABRAHAM RAISED HIS SON." | its text (4.3%) | as in Scene 1 |

On every frame of each insert the smallest text on the subject is at
least `TEXT_MIN` (3%) of the frame's height, measured on the scroll's
lines and the phone's screen as they are drawn on that frame.

What "frames well" leaves to a person: nothing checks that another prop does not cover the subject
(in Scene 4 the knife handle covered the LIVE button until a pose step
was added to the cue `s04_picks_up_phone`).

## Findings recorded while building the baseline

**Updaters in dry-run mode (Milestone 1, task 7).** Manim does advance
updaters on every frame in the dry-run mode the tracer uses: with Manim 0.22.1
(Cairo renderer) a dry run calls each updater at exactly the same times and
with the same `dt` as a render that writes video. So the tracer does not need
to step constraints itself. One thing to plan for in Milestone 3: the tracer
looks at the scene only before and after each `play`, so it does not yet *see*
the frames in between. Recording a `sampled` piece needs a per-frame sampler,
and an updater is a workable place for one.

**A frame listener that outlived its block (fixed in the timeline
hardening).** `pam.timeline.Block.run` adds a scene updater while a tracer is
listening and removed it with `scene.remove_updater(self._tick)`. Manim removes
updaters by identity, and `self._tick` is a new bound-method object each time it
is written, so the updater stayed. After the first timed block of a scene the
tracer went on recording frame by frame to the end of the scene. The positions
were right, and ordinary renders were never affected, because the updater is
only added while tracing; but the trace was larger than it had to be, and moves
after the block lost their pose names and easing in it. `Block.run` now keeps
the bound method in a variable and uses it for both calls. Two golden traces
were recorded again for this: in `abe-isaac_overlap_timeline.json` only
`stats.plays` changed (96 to 90: the six frames of the closing wait are one
wait again), and in `abe-isaac_scene2-gags.json` Abraham's four-frame slip is
one piece with its easing instead of four straight ones.

**The `scale` action does not run (found in the timeline hardening, not
changed).** `act_scale` in `pam/actions.py` calls `fig.set_scale(...)`, and no
figure class has that method, so a `{"action": "scale", ...}` step raises
`AttributeError`, at the top level and in any `parallel` block. No fixture or
screenplay in the repository uses it; characters get their scale from the
`cast` step. It is listed among the actions a timed block can run, and the
validator accepts it.

**Stateful props (Milestone 4, Stage 4a).** Five things turned up.

- *A display may only be redrawn between two plays* (the same Manim rule as
  for bubbles in timed blocks). A viewer count that climbs is therefore one
  play per frame, and the phone's screen is redrawn after each.
- *A prop moved by something else's updater is not redrawn.* Manim paints
  everything before the first "moving" mobject once per play. A prop kept
  on an attachment gets an updater of its own that does nothing, which marks
  it as moving.
- *A prop on a hand and a hand on a prop.* Attachments are placed, then the
  contact constraints are solved, then attachments are placed again, on
  every frame, so a prop in a constrained hand and a hand constrained to a
  held prop both come out right.
- *A turned blade's bounding box is not centered on the blade.* Manim keeps
  the box center on the target; the Blender model is shifted back by the
  difference at each angle (up to 0.016 units).
- *The elevator's doors slide inside its own outline*, so the prop's box in
  the trace never showed them opening. Its state does now.

**The scroll (Milestone 4, Stage 4b).** Four things turned up.

- *Text is redrawn between plays, like a display.* Writing over `frames`
  is one play per frame, as a climbing viewer count already was.
- *A prop whose shape changes must not be followed by its bounding box.*
  Rolled, open and trailing, the scroll's box is in three different
  places relative to the hand. The scroll is kept on its attachment by its
  grip (its near roller), the tracer records the grip as its position, and
  the Blender model is built from the grip, so the hold offset Blender
  uses does not change when the scroll unrolls in the hand.
- *A prop that had not yet arrived on its attachment traveled from where
  it was built (fixed).* A prop attached to a character is put on its
  attachment on the first frame played after the character is on stage.
  If the very next step moved the prop over some frames, the move began
  from where the prop was built (the middle of the stage), and the trace
  had no record of its first attachment. This was Stage 4a behavior, for
  every stateful prop. A prop that is about to travel is now put on its
  attachment first, and so is what it is attached to (the quill in the
  satchel on Abraham's hip). No golden trace changed with the fix: in the
  seven fixtures before this stage no prop moves in that situation.
  `test_a_prop_moved_right_after_its_holder_appears_starts_on_its_attachment`
  in `test_prop_trace.py` checks it.
- *Fonts.* Installing the TeX fonts needed to rebuild
  `pam-reference-book.pdf` (Debian's `texlive-fonts-extra`) also installs
  `fonts-croscore`, and fontconfig then gives Cousine instead of Liberation
  Mono for "Courier New". Its metrics are the same, so the text probe still
  passes and the comparison stays strict, but the glyph outlines in the
  traces differ and two legacy golden traces fail. Check
  `fc-match "Courier New"` before recording or comparing golden traces.

The README's "Stateful props" examples named `open_doors` and `close_doors`
as actions. Those are methods of the prop; the actions are `elevator_open`
and `elevator_close`. The examples are corrected.

**The rope (Milestone 4, Stage 4c).** Seven things turned up.

- *A rope's shape is not in the books.* The `World` (and so the
  validator and the ledger) keeps the rope's state and attachments; its
  shape follows from them and is worked out on every frame by the
  `StateManager`. So the ledger stays small and the completion test
  needs no geometry.
- *Changing shape in place is a travel too.* Pulling the knot tight
  changes no attachment, only the state. A rope that is where it
  belongs would take the new state's shape at once when it is put on
  its attachment again at the start of the step, so a step with
  `frames` keeps the shape the rope had and turns it into the new one
  over its frames, as a move does.
- *A blend of two shapes shrinks.* Blending a coil into a loop point by
  point made the rope shrink to a small knot halfway across.
  `_blend_shapes` moves its middle in a straight line and its points
  toward their new places, while its size goes evenly from one shape's
  to the other's. In the fixture and in Scene 4, Isaac's turn to hold
  out his wrists and the rope's move from Abraham's shoulder now share
  their frames (one timed block, both 18 frames), so the rope arrives as
  his hands do. Aiming at a loop round his wrists while they were still
  far apart stretched the rope across his body on the way, so a rope
  going round joints it was not round before aims at a loop drawn in
  toward their middle that opens out as it arrives.
- *A rope is not held.* A prop on a character emits `prop_attach` and
  the tracer turns that into a hold, which Blender follows with a
  constraint on the hand. A rope's pieces have no holds: their control
  points already say where they are, frame by frame, and Blender keys
  them directly.
- *Blender does not recompute automatic handles on animated points.*
  With `AUTO` handles the curve kept the handles of its first shape and
  drew spikes as the points moved. `trace2blender.py` works out smooth
  (Catmull-Rom) handles itself and keys them with the points; the curve
  passes through every control point.
- *`figure_frames` is exact only at the ends of moves outside timed
  blocks.* The tests that follow the rope on Abraham's shoulder as he
  walks, and round Isaac's wrists as he moves his arms, check the
  frames on which it is exact.
- *Fonts, again.* The reference book needs `newtx` (in Debian's
  `texlive-fonts-extra`), `binhex.tex` (`texlive-plain-generic`) and the
  TeX Gyre metrics (`tex-gyre`). Installed with
  `apt-get install --no-install-recommends`, `fonts-croscore` is not
  pulled in and "Courier New" still falls back to Liberation Mono, so
  the golden traces stay strict.

**The referee report on Milestone 2.** `test_timeline_hardening.py` holds what
came out of it:

- Overlap detection compared only neighboring moves of a figure, so a long move
  with two short ones inside it was reported once. Every pair is compared now.
- Two steps that set the whole pose of one figure on the same frames are an
  error, and so is a block whose `frames` is shorter than its steps need. Both
  were warnings. The player is unchanged and plays such a block.
- A camera cut in the middle of a move framed the figure where the move would
  leave it: one stride ahead in a walk, the whole distance in a sliding
  `morph`. It frames the drawn figure now. A cut on a figure at rest is
  unchanged. One cut in `abe-isaac_scene2-gags.json` falls on the first frame
  of Abraham's pop and moved with this (camera center 0.24 to -0.72).
- On a frame where one move ends, another begins, the camera cuts and a
  constraint is released, the order is: ends, constraints, starts.
- At 30 fps an untimed action can leave the scene half a frame off the 15 fps
  clock. Lengths were already exact. Reported frame numbers could be off by
  one, and a constraint with `frames` could be released half a frame early or
  late; frames are now counted from where the block or the constraint starts.
  The tracer always runs at 15 fps, where this cannot happen.
- A `fade_out` on a figure that another step is moving is still a warning. It
  holds the figure still where it is while it fades.

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

**Fountain+ cues and fitted inserts (Milestone 5).** Seven things turned up.

- *The compiler dropped every insert.* Without a project, `fountain2pam.py`
  places a camera marker where a speaker's clip ends, with the clip's last
  `CAMERA` note; a `CAMERA` note between two action lines is overwritten by
  the next one before any clip ends. Compiled that way, none of the six
  inserts of Draft 3 survives (its markers are all wide or medium shots). This is left alone (it would change
  the output for every screenplay); in project mode the cut is where the
  note is.
- *The legacy insert misses props low on the stage.* It is 7 units wide and
  centered at y = 1.5, so a phone propped on a rock (y about -2) is below
  the frame. Fitted shots (`"fit": "bounds"`) are opt-in, so the legacy
  insert is unchanged.
- *A broken knife moves out of a frame set at the cut.* At the cut the knife
  is whole in two hands; the blade then drops 2.2 units into the bowl.
  Framing the box at the cut would show the hands and lose the blade, so a
  fitted shot also holds where the shot's steps send its subject before the
  next cut. The steps are read from the screenplay, not simulated: a target
  that moves during the shot (Isaac's hand, as he straightens) is taken
  where it is at the cut, which the margin covers here.
- *One shot was too wide for the knife.* Holding both the hands and the
  bowl 2.2 units below made a 5.2-unit medium cut-in. The script now has
  two inserts (the knife, then the bowl), the cue makes the second cut on
  frame 6 of the break block, and a move counts only in the shot it ends
  in. The screenplay's CAMERA notes after a beat stand for the cuts its
  cue makes, so they are not cut twice.
- *A fitted cut needs its subject.* Scene 5 opens on an insert of the
  phone in Abraham's hand, before he fades in. At first the opening cut
  came after the scene's `before` steps (18 frames of wide shot); it now
  comes first, and the phone is found in the hand of Abraham as his
  `fade_in` will build him. Played in that order, the setup left 12
  frames of empty sky in the insert, so Abraham now fades in first: 6
  frames of him drawing in at the insert's size, then the phone, while
  the rock, the altar and Isaac fade in out of the shot. A `fade_in`
  always takes frames (an edge pass, then a dot pass), so a scene that
  opens on a prop in a hand opens on the hand drawing in.
- *A prop that appears in a hand is traced at the origin for a moment.*
  When a figure fades in holding a prop, the trace has the prop at the
  origin and moving to the hand during the next step that is not a
  timed block (frames 6 to 9 of Scene 5; on main the scroll in Scene 2
  and the phone in Scene 6 do the same). The render has it in the hand
  on every frame. This is left alone (fixing it would change traces);
  the insert tests skip the frames of that move. A subject that is declared but not yet on its
  attachment is framed where the prop-state books keep it.
- *The trace follows a scroll by its grip*, not by the center of its
  bounding box, so the completion test places the scroll's text on the
  grip.
- *Finding a character cue.* The compiler finds an element's line in the
  file by matching the start of the line, so `ISAAC` also matches the
  action line `Isaac finally looks up.`; that is left as it is for the
  notes it already fires, and beat notes use the line that is the cue
  itself.
- *`fountain2pam.py` never had PAM's prop types.* It loads `pam/props.py`
  under a stand-in Manim to read `PROP_TYPES`, the import fails
  (`linear` is not defined), and it falls back to ten built-in names, so
  it does not know `knife`, `phone`, `scroll`, `rope`, `bowl` or `altar`.
  This is left alone (it would change its output); the stand-in module
  was also left in `sys.modules`, which mattered only in a process that
  imports Manim afterwards, and it is now removed.

## Manim version

`requirements.txt` pins Manim 0.22.1, the version the golden traces were
recorded with. The timed blocks rely on three things about that version: a
mobject added or removed in the middle of a play is not redrawn, an animation's
`finish()` puts a constrained joint back where the pose has it, and a fade-out
expects its mobject in the scene. `pam/timeline.py` works around each inside
the block runner. To try a newer Manim, install it and run `python -m pytest`:
`test_timeline_blocks.py`, `test_timeline_hardening.py` and
`test_choreography.py` exercise all three, and `test_golden_traces.py` says
whether anything else moved.

## The Stage 6a checks (Milestone 6: Scenes 1 and 2 performed)

The roadmap's acceptance rows for Scenes 1 and 2 are judgments
("reads clearly"); `test_performance.py` checks what can be measured,
on a trace of each scene:

| Scene | Gag | What the trace must show |
|---|---|---|
| 1 | Abraham writes | the text is written over 30 frames while his quill hand moves |
| 1 | the insert | at least 24 frames on a fitted insert, with the quill off the line |
| 1 | the question mark | the period becomes `?` on the second insert; a hold of 12 frames or more to read KNIFE?, with nothing over the line |
| 1 | the THUD | his head rises during the startle and he ends looking toward the cave |
| 2 | scale contrast | Isaac's height over Abraham's is 0.80/0.48, on one floor, in one shot |
| 2 | the lift | the barbell above Isaac's head, then on the floor as THUD! comes |
| 2 to 6 | the barbell becomes the altar | hidden in the cave (1), carried off (2), on his shoulders (3), then in Scene 4 on the ground at the THUD and taken apart: boulders apart, the log across their tops, the left boulder straightened by Abraham and put back crooked by Isaac; an altar in the ledger through Scene 6, and never a barbell again |
| 2 | counting | five finger taps (a beat each), none on "And then...", then the hand held up to his face |
| 2 | the wrist pull | his hand on Isaac's wrist for the whole pull, and Isaac's feet do not move |
| 2 | the fall | flat on his back, then a comic hold of 9 frames or more |
| 2 | the cork-pop | the hands together through the pop, Abraham off the ground, then upright |
| 2 | the hug | the arms do not reach around; he is still holding on during "Have you thought about a diet?" |
| 2 | the broken knife | the handle in Isaac's hand and the blade in the bowl |
| 1, 2 | dialogue | every sentence of the script is spoken in a bubble, and no bubble says words the script does not |

They also check that every cue of the two scenes is compiled, that the
Scene 2 routines are on beat notes of action lines, and that the two
scenes end where the ledger says. The contact sheets in the pull
request are the visual check.

## The Stage 6b checks (Milestone 6: Scenes 3 and 4 performed)

`test_performance_6b.py` measures, on a trace of each scene, what the
roadmap's two acceptance rows (Scene 3: "Isaac's effortless movement
contrasts with Abraham's struggles"; Scene 4: "props are staged
correctly; rope and phone interactions are clear") come down to:

| Scene | Gag | What the trace must show |
|---|---|---|
| 3 | the climb | Isaac covers far more ground than Abraham, moving forward on every frame of his stride; Abraham hunches lower than he stands and makes no headway for 8 frames or more |
| 3 | catching his breath | Abraham bent over and heaving while Isaac does not move a joint |
| 3 | the rock | Isaac goes over it in one bound, his feet above it wherever they are over it; Abraham's climb takes four times as long, mostly on hands and knees, with one slide back to the ground; he stands on its top before he slips |
| 3 | the catch | the hand on the collar on every frame from the catch to the set-down, his feet off the ground all that time, the barbell on Isaac's shoulders; he kicks; all five lines in between are said while he hangs; he is set down on his feet and let go |
| 3 | walking on | both off stage, to the left, at the end |
| 4 | the altar | built beside Isaac: neither of his feet is inside it while it goes up |
| 4 | the phone | upright on the top of the rock, put there by Isaac crouched beside it |
| 4 | the heroic pose | Isaac's fists on his hips; Abraham one fist on a hip and the other hand above his neck; side by side |
| 4 | the rope | Isaac seated on the log with his feet on the ground while it is wound round his wrists; loose, tied, tightened, in that order; Abraham's hands near the knot; the yank pulls them away from it on the frames the rope goes tight |
| 4 | lying back | his head drops; his elbows on the log; his wrists together |
| 4 | the phone again | Abraham's hand at the phone on its rock when he picks it up, and the phone in his hand, by the rock, at the end of the scene |
| 3, 4 | dialogue | every sentence of the script is spoken in a bubble, and no bubble says words the script does not |

The same file traces `catch_by_collar` and `tie_wrist_loop` in small
scenes at four combinations of sizes (as cast; Isaac 1.30 wide; Isaac
larger all over; Abraham 0.70, nearly as tall): the collar is held with
no shortfall and the feet clear the ground, and the hands loop round the
wrists at least twice, within reach, without falling short.
