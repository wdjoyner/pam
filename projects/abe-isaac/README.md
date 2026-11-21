# Abraham and Isaac, Revisited: the PAM project

The six scenes of the short, compiled from the screenplay (Milestone 5
of *PAM: The Road to Blender*), with the prop continuity of Milestone 4
(Stages 4a, 4b and 4c): the knife, the phone, the scroll and the rope.
Scenes 1 to 4 are performed (Milestone 6, Stages 6a and 6b): every gag
is acted in four phases (`perform`), with mannerisms (`react` with
`fragment`), holds, and speech bubbles. Scenes 5 and 6 are still
blocking for the props (Stage 6c): the characters stand, walk a little
and speak their lines, and the knife, the phone, the scroll and the rope
do everything Draft 3 of the script has them do.

| File | What it holds |
|---|---|
| `project.json` | where everything is: the screenplay, the cue file, the sidecar, and the scene files in order |
| `source/script.fountain` | a copy of the screenplay; the authoritative literary version is `shorts/abe-and-isaac/script.fountain` in `writing-guides`, and `project.json` records the commit it was copied from and its sha256 |
| `cues/animation_cues.json` | the hand-authored choreography, keyed by the beat notes in the screenplay (`[[beat: s02_slings_rope]]`), and what each scene starts and ends with |
| `pam_sidecar.json` | the cast, and the `continuity` block: the scenes in order, the props that carry over (`satchel`, `knife`, `phone`, `scroll`, `quill`, `rope`), and the ledger PAM writes |
| `scene1.json` ... `scene6.json` | the scenes, **compiled**: edit the screenplay or the cues, not these |

```bash
# from the repository root
python fountain2pam.py --project projects/abe-isaac          # compile the scenes
python fountain2pam.py --project projects/abe-isaac --check  # are they up to date?
./pam-validate --project projects/abe-isaac                  # all six, in order, no rendering
./pam-render --script projects/abe-isaac/scene2.json         # one scene
```

This is a lighter layout than the roadmap's suggestion (`source/`,
`cast/`, `props/`, `cues/`, `scenes/`): the cast, the prop definitions
and the continuity ledger stay one file, `pam_sidecar.json`, as
Milestone 4 built them, and the scene files stay next to it, where the
player looks for its sidecar.

## Scenes 1 and 2 (Milestone 6, Stage 6a)

The cues of Scenes 1 and 2 are a performance, not blocking. Each gag is
a `perform` (four phases, anticipation, action, reaction, recovery, with
their lengths in one table), and most acted lines of dialogue are one
too: the speaker gets into a gesture, says the line, and settles back.
The script in `writing-guides` has a beat note on every line PAM acts
(27 new in Scene 2, and one split paragraph in Scene 1; see its revision
log). To retime a gag, change a number in its `phases` and recompile.

| Beat | What is acted |
|---|---|
| `s01_takes_quill`, `s01_writes` | an opening hold; the quill from the satchel; the line written while the hand moves along it; a nod; the quill lifted off the page |
| `s01_insert` | 27 frames on the line |
| `s01_studies` | he bends over the scroll and shakes his head |
| `s01_question_mark` | on the second insert, the quill comes down, the period becomes a question mark, and the quill lifts away for 18 frames |
| `s01_thud` | a pleased nod; THUD! from the cave and a jump; he stares toward it; quill away, scroll rolled into his belt |
| `s02_checks_clips` | Isaac lifts the barbell overhead, sets it down (THUD!), takes out his phone and strolls to his spot by the magazines |
| `s02_abraham_enters` | Abraham walks in from the entrance |
| lines of dialogue | a gesture each: a shrug, a pat on the chest, a finger up to God, a wagging finger, a thumb toward outside, hands to the cheeks, palms up, hands on hips, a hand to the chin |
| `s02_looks_up` | a beat, the phone down, a stare |
| `s02_magazine`, `s02_persona` | the phone into his pocket, the top magazine held up beside his head for both sentences, then back on the stack |
| `s02_counts`, `s02_the_list`, `s02_out_of_fingers` | the hand raised; five taps of a finger, one per item; nothing on "And then..."; the hand brought up to his face and stared at |
| `s02_buzz` | BZZZ at Isaac's hip, a jump, the phone out, a read |
| `s02_pull` | Milestone 3's `pull_immovable` (the action phase), `slip_on_back` (the reaction) and a comic hold while Isaac looks down (the recovery) |
| `s02_cork_and_hug` | `cork_pop_up` (offer and accept, the 3-frame pop, the landing and the image held) and `mismatched_hug`, still holding on |
| `s02_diet` | the line said into Isaac's side; then he lets go and steps back |
| `s02_draws_knife` ... `s02_handle_down` | the Stage 4a knife, with his hand going to the satchel and the knife held out; Isaac looks at the blade, the magazines, his phone |
| `s02_got_it` | a finger up: an idea |
| `s02_into_satchel`, `s02_slings_rope`, `s02_pockets_phone` | Isaac takes the barbell under his arm and strides out past his father, who gathers the knife into the satchel, picks up the rope by the entrance and hurries after him |

Scene 1 has a rock for Abraham to sit on, and Scene 2 two `magazine`
props (a stack, and the top one with ISAAC THE INVINCIBLE on its
cover), all local to their scenes (`before` steps). Uncued lines get
their bubble side from the cue file (`scenes.scene2.say`).

The barbell is a continuity prop (in the sidecar's continuity block and
the ledger, at the author's request): hidden in the cave in Scene 1 (the
THUD comes from it); lifted, set down and carried off by Isaac in Scene
2; on his shoulders in Scene 3; and in Scene 4 dropped (THUD) and taken
apart into the altar, the two boulders set apart and the log laid
across them (`s04_builds_altar`, state `altar`; the left boulder is
left crooked). It is the altar in Scenes 4 to 6, which no longer
declare an `altar` prop, and the blade sticks in its log in Scene 5.
The script was changed to match (writing-guides revision log, "the
barbell becomes the altar").

The Milestone 3 fixture `abe-isaac_scene2-gags.json` has two lines that
are not in the script ("Up you get." and "My boy."); the scene does not
use them.

## Scenes 3 and 4 (Milestone 6, Stage 6b)

Scenes 3 and 4 are performed the same way. The script has a beat note on
every line PAM acts (24 new; see its revision log), and the scene files
have no `# REVIEW` comment left: every action line is staged.

Scene 3 travels from right to left, as Scene 2 left the cave, past one
rock (a prop local to the scene). Isaac's bubbles are on his right and
Abraham's on his right (`scenes.scene3.say`): Isaac is always to his
father's left.

| Beat | What is acted |
|---|---|
| `s03_climb` | an empty path; Isaac strides in at an even pace, the barbell riding on his shoulders, arms swinging; Abraham staggers in after him in short walks, hunched over between them (pose `stagger`) |
| `s03_the_plan` | Isaac lays out the plan looking back at his father, strolls on and waits again; Abraham plods after him |
| `s03_catch_breath` | Abraham bent double, hands on knees, heaving (`catch_breath`, tic `pant`); Isaac stands and waits without moving a joint |
| `s03_morality` ... `s03_no_improvising` | the line gasped bent over; a headline in lights (`headline`); a nod and a wagging finger |
| `s03_bounds_over_rock` | Isaac crouches and bounds over the rock in one leap (`hop_crouch`, `hop_tuck`), strolls on and turns to watch |
| `s03_climbs_rock` | Abraham's hands on the rock (`climb_reach`); he hauls himself up, slides back to the ground, hauls again, and crawls along the top (`crawl_a`, `crawl_b`) |
| `s03_father_of_nations` | he rises up on his knees on the rock to say it, a hand on his chest (`kneel_proud`, tic `chest_pat_r`) |
| `s03_catch` | `catch_by_collar`: he stands up on the top (`proud`) and steps to its edge; his sandal slips (the `slip`, pose `topple`); Isaac's hand takes him by the collar and hoists him up (`catch`); he kicks and goes limp (`dangle`); the hold is left in force |
| `s03_lamb` ... `s03_provide` | said while he hangs: Isaac looks about him; Abraham shrugs; the barbell bounces on Isaac's shoulders (`bar_bounce`); a finger up to heaven (`dangle_point_up`). "He provided the knife." is said flat |
| `s03_sets_down` | a beat; `catch_by_collar` with only its `set_down`; Abraham gives himself a shake; Isaac walks on and Abraham staggers after him |

In Scene 4 Isaac used to stand where the altar is built; he now drops
the barbell, steps to its end (x 3.3), and builds the altar beside him.
Isaac's bubbles are on his right and Abraham's on his left.

| Beat | What is acted |
|---|---|
| `s04_builds_altar` | Abraham, still blown from the climb, pants; Isaac lifts the barbell off his shoulders and drops it (THUD!, and Abraham jumps); he steps to its end, squats, and the altar goes up beside him; Abraham straightens the left boulder, Isaac comes round and nudges it back with his foot (`foot_nudge`); a shrug and a nod |
| `s04_props_phone`, `s04_heroic_pose` | Isaac crouches at the little rock (`crouch_reach_r`) and props his phone on it; back by the altar he strikes the pose (`hero`), and Abraham tries it (`hero_shade`); the image is held |
| `s04_handle_not_blade` | a finger up |
| `s04_takes_pieces_out`, `s04_blade_into_satchel` | the Stage 4a steps, with his hand going into the satchel and a look at the pieces |
| `s04_sits_on_altar` | Isaac sits back on the log, facing his father (`sit_side`), and holds out his wrists (`sit_wrists_out`) |
| `s04_winds_rope` | `tie_wrist_loop`: Abraham takes the coil from his shoulder as he steps up, winds it round Isaac's wrists in loops that get bigger and wilder (the rope goes from his shoulder to the wrists, state `tied`, on the same frames), fiddles at the knot and lets go; the knife handle stays in his other hand |
| `s04_looser` ... `s04_before_you_were_born` | a shake of the head; "I'm tying a bow." said fiddling at the knot (`tie_wrist_loop`, only `knot`); a nod and a shrug; chin up, hand on chest (`proud`) |
| `s04_yanks_knot` | `tie_wrist_loop`, `knot` and `yank`: the knot yanked tight in three frames (state `tightened` on the same frames), Abraham jerking back; Isaac tugs at it (`wrist_tug`); it holds; a shrug; he lies back on his elbows (`recline_elbows`) |
| `s04_press_red` | both tied hands point at the phone (`recline_point`) |
| `s04_picks_up_phone`, `s04_red_button` | Abraham walks to the rock, crouches for the phone (`crouch_reach_l`), comes back and holds it out; the insert holds the LIVE button 18 frames |
| `s04_rehearses` | a nod; he counts on his fingers, phone in one hand and handle in the other (`count_tap_r`), and his hands shake (`tremble`); he turns and goes to the rock to lean the phone back against it, and the scene ends with him crouched there |

The prop transitions of both scenes are the Milestone 4 steps, in the
same order: the ledger is unchanged.

Two things for Stage 6c: Scene 5 is "CONTINUOUS", and still opens with
Isaac standing at the cast position with his wrists held out and Abraham
at x -1.2; Scene 4 now ends with Isaac lying back on the altar and
Abraham crouched at the rock with the phone.

## How the scenes are compiled

Each scene heading of the screenplay is one scene file. A paragraph or a
line of dialogue with a beat note compiles to its cue, copied as it is;
everything else compiles as `fountain2pam.py` always compiled it (lines
of dialogue become `say` steps; prose it cannot animate is left as a
`# REVIEW` comment). The cast and props come from the sidecar and the
cues, never from the compiler. There is a camera cut wherever the
screenplay has a `CAMERA` note, and every insert (the scroll, the knife,
the bowl, the phone) is framed from its subject's bounding box.

In Milestone 5 the 42 cues were the steps of the Milestone 4 scene files
(Stage 6a has since rewritten those of Scenes 1 and 2 and added 28 more,
70 in all), moved into the
cue file unchanged. They now play in the screenplay's order, with its
dialogue between them, so a few run in a different order than they did
(in Scene 2, Abraham enters after the phone and the rope are in place,
as the script has it). There are three other differences:

- the Stage 4a sequence `s02_knife` is split at the screenplay's beats
  (`s02_draws_knife`, `s02_knife_breaks`, `s02_handle_down`,
  `s02_into_satchel`); its steps are played at the top level, in the
  same order, and the contact it starts is released inside the break
  block as before;
- the break block `s02_break` has two more steps: a cut to an insert on
  the bowl (`bowl+knife.blade`) on frame 6, as the blade falls, and a cut
  to the wide shot on frame 18, where Isaac says his line. The
  screenplay's CAMERA notes for those two shots stand for these cuts. The
  blade's line has its own beat, `s02_blade_in_bowl`, with an empty cue
  (the block already drops the blade);
- Scene 5 opens on the insert of the phone, and its `before` steps fade
  Abraham in first (6 frames, drawn in at the insert's size), then the
  props and Isaac, out of the shot, while the phone is on screen;
- in `s04_picks_up_phone` Abraham then holds the phone out (pose
  `reach_side_l`), so that the knife handle in his other hand does not
  cover the LIVE button in the insert.

Validating or playing a scene writes its closing entry into
`pam_sidecar.json`. The entries in the repository are the ones these
scenes produce (byte for byte the ones the hand-authored Milestone 4
scenes produced), so doing either leaves the file unchanged. No scene
overrides the ledger: each opens exactly as the one before left it.
`./pam-validate --project` reports no errors; its warnings are the
`# REVIEW` comments, the prose the cues do not choreograph yet.

The knife and the phone at the end of each scene are tabulated in
`tests/README.md` ("The Milestone 4 completion test"), the scroll in
"The Stage 4b completion test", the rope in "The Stage 4c completion
test", and the compilation and the inserts in "The Milestone 5
completion test".

The scroll follows Draft 3 with the scroll-continuity edits proposed in
`writing-guides` (pull request 10): in Scene 1 Abraham writes the line,
turns its period into a question mark, rolls the scroll up and tucks it
into his belt; it stays there until Scene 6, where he takes it out,
unrolls it, crosses out THE KNIFE? and writes HIS SON. in its place, and
runs with it open in his hand so that it trails. The quill lives in the
satchel; he takes it out to write and puts it back (a blocking choice).

The rope follows Draft 3 with the rope-continuity edits proposed in
`writing-guides`: it lies coiled by the cave entrance in Scene 2 (in
Scene 1 it is in the cave, out of sight), and Abraham slings it over his
shoulder as he follows Isaac out; he carries it there in Scene 3; in
Scene 4 Isaac holds out his wrists and Abraham winds the rope round them
and yanks the knot tight; it stays tight on Isaac's wrists through Scene
5; and in Scene 6 Isaac flexes, it snaps, and its two halves fly off his
wrists and land on either side of the altar, where they lie to the end.
Isaac holds his wrists out (pose `reach_forward`) from the tie to the
snap, so Scenes 5 and 6 open with him in that pose (a blocking choice).
