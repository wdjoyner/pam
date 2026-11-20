# Abraham and Isaac, Revisited: the PAM project

The six scenes of the short, compiled from the screenplay (Milestone 5
of *PAM: The Road to Blender*), with the prop continuity of Milestone 4
(Stages 4a, 4b and 4c): the knife, the phone, the scroll and the rope.
They are blocking for the props, not yet the animatic (that is
Milestone 6): the characters stand, walk a little and speak their lines,
and the knife, the phone, the scroll and the rope do everything Draft 3
of the script has them do.

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

## How the scenes are compiled

Each scene heading of the screenplay is one scene file. A paragraph or a
line of dialogue with a beat note compiles to its cue, copied as it is;
everything else compiles as `fountain2pam.py` always compiled it (lines
of dialogue become `say` steps; prose it cannot animate is left as a
`# REVIEW` comment). The cast and props come from the sidecar and the
cues, never from the compiler. There is a camera cut wherever the
screenplay has a `CAMERA` note, and every insert (the scroll, the knife,
the phone) is framed from its subject's bounding box.

The 41 cues are the steps of the Milestone 4 scene files, moved into the
cue file unchanged. They now play in the screenplay's order, with its
dialogue between them, so a few run in a different order than they did
(in Scene 2, Abraham enters after the phone and the rope are in place,
as the script has it). There are three other differences:

- the Stage 4a sequence `s02_knife` is split at the screenplay's beats
  (`s02_draws_knife`, `s02_knife_breaks`, `s02_handle_down`,
  `s02_into_satchel`); its steps are played at the top level, in the
  same order, and the contact it starts is released inside the break
  block as before;
- the break block `s02_break` has one more step, a cut to the wide shot
  on frame 18, where Isaac says his line;
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
