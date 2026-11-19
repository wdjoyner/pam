# Abraham and Isaac, Revisited: prop continuity

Six scenes that take the knife, the phone, the scroll and the rope
through the film, for Milestone 4 of *PAM: The Road to Blender* (Stages
4a, 4b and 4c).
They are blocking for the props, not the animatic (that is Milestone 6):
the characters stand, walk a little, and say one or two lines, and the
knife, the phone, the scroll and the rope do everything Draft 3 of the
script has them do.

| File | What it holds |
|---|---|
| `pam_sidecar.json` | the cast, and the `continuity` block: the scenes in order, the props that carry over (`satchel`, `knife`, `phone`, `scroll`, `quill`, `rope`), and the ledger PAM writes |
| `scene1.json` ... `scene6.json` | the scenes |

```bash
# from the repository root
./pam-validate --project projects/abe-isaac          # all six, in order, no rendering
./pam-render --script projects/abe-isaac/scene2.json # one scene
```

Validating or playing a scene writes its closing entry into
`pam_sidecar.json`. The entries in the repository are the ones these
scenes produce, so doing either leaves the file unchanged.

No scene overrides the ledger: each opens exactly as the one before
left it, and `./pam-validate --project` reports no warnings.

The knife and the phone at the end of each scene are tabulated in
`tests/README.md` ("The Milestone 4 completion test"), the scroll in
"The Stage 4b completion test", and the rope in "The Stage 4c
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
