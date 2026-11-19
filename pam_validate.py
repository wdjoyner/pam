"""
pam_validate.py — check PAM JSON screenplays without rendering a video.

Usage:
    python pam_validate.py scene.json [more.json ...] [options]
    ./pam-validate scene.json

Options:
    --strict       treat warnings as errors
    --quiet        print errors only (and the one-line summary)
    --json         print the report as JSON instead of text
    --frames       also list every duration that is not a whole number of
                   frames at 15 fps, with the rounded value (notes; they
                   never fail a screenplay)
    --no-sidecar   do not merge pam_sidecar.json / PAM_SIDECAR first (and
                   so use no continuity ledger)
    --no-ledger    read the continuity ledger but do not write this
                   scene's closing entry to it
    --project P    validate every scene of a project in playing order: P is
                   the sidecar file (or the folder holding
                   pam_sidecar.json) whose "continuity" block lists the
                   scenes.  Each scene opens as the one before left it,
                   so the prop continuity of a whole film is checked in
                   one pass, without rendering.  No files are named.

Errors: unknown actions, invalid joint names, negative durations,
references to characters or props that do not exist at that step, and
steps of a timed parallel block that cannot run on the frame clock, and
prop transitions that cannot happen (pam/prop_states.py).
Warnings: unresolved "# REVIEW" and "# PATCH" comments from
fountain2pam.py, steps the player skips, every place where a scene
overrides the continuity ledger, and similar.  See
pam/validate.py for the full list and pam/action_specs.py for the
tables it checks against.

Exit status: 0 when every file is valid, 1 when any file has an error
(or a warning, with --strict), 2 for a usage error.

Run it from the PAM repository folder (or put that folder on PYTHONPATH)
so that the ``pam`` package can be imported.
"""
import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pam-validate",
        description="Check PAM JSON screenplays without rendering.")
    parser.add_argument("files", nargs="*", help="PAM JSON screenplay(s)")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors")
    parser.add_argument("--quiet", action="store_true",
                        help="print errors only")
    parser.add_argument("--json", action="store_true",
                        help="print the report as JSON")
    parser.add_argument("--frames", action="store_true",
                        help="list durations that are not a whole number "
                             "of frames at 15 fps")
    parser.add_argument("--no-sidecar", action="store_true",
                        help="do not merge the cast-and-props sidecar")
    parser.add_argument("--no-ledger", action="store_true",
                        help="do not write the continuity ledger")
    parser.add_argument("--project", metavar="P",
                        help="validate every scene the sidecar P (a file, "
                             "or a folder holding pam_sidecar.json) lists "
                             "in its continuity block, in order")
    args = parser.parse_args(argv)
    if bool(args.project) == bool(args.files):
        parser.error("give screenplay files, or --project, not both")

    from pam.validate import validate_file, validate_project

    if args.project:
        reports = validate_project(args.project, frames=args.frames,
                                   ledger=not args.no_ledger)
    else:
        reports = [validate_file(p, sidecar=not args.no_sidecar,
                                 frames=args.frames,
                                 ledger=not args.no_ledger)
                   for p in args.files]
    failed = any((not r.ok) or (args.strict and r.warnings)
                 for r in reports)

    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        for r in reports:
            print(r.format(show_warnings=not args.quiet))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
