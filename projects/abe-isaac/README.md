# Abraham and Isaac, Revisited: prop continuity

Six scenes that take the knife and the phone through the film, for
Stage 4a of Milestone 4 of *PAM: The Road to Blender*. They are blocking
for the props, not the animatic (that is Milestone 6): the characters
stand, walk a little, and say one or two lines, and the knife and the
phone do everything Draft 3 of the script has them do.

| File | What it holds |
|---|---|
| `pam_sidecar.json` | the cast, and the `continuity` block: the scenes in order, the props that carry over (`satchel`, `knife`, `phone`), and the ledger PAM writes |
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
`tests/README.md` ("The Milestone 4 completion test").
