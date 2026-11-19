"""
Does Manim still advance updaters on every frame in dry-run mode?

Roadmap Milestone 1, task 7.  Milestone 3 keeps a hand on a moving
wrist with per-frame constraints, and ``pam_trace.py`` runs the player
with ``dry_run=True``.  If dry-run mode skipped the per-frame updates,
the tracer would have to step constraints itself.

Answer (Manim 0.22.1, Cairo renderer): it does advance them.  A dry run
calls every updater at exactly the same times, with the same ``dt``, as
a render that writes video; only the frame encoding is skipped.  These
tests pin that down so a Manim upgrade that changes it is noticed.
"""
import pytest
from manim import Dot, Scene, RIGHT, UP, config, tempconfig


def _run(dry_run, media_dir):
    calls = []          # (scene time, dt) at every updater call
    result = {}

    class Probe(Scene):
        def construct(self):
            driver, follower = Dot(), Dot()

            def follow(mob, dt):
                calls.append((round(self.renderer.time, 4), round(dt, 4)))
                mob.move_to(driver.get_center() + UP)

            follower.add_updater(follow)
            self.add(driver, follower)
            self.play(driver.animate.shift(3 * RIGHT), run_time=1.0)
            result["after_play"] = follower.get_center().copy()
            self.wait(0.4)

    with tempconfig({"dry_run": dry_run, "quality": "low_quality",
                     "disable_caching": True, "verbosity": "ERROR",
                     "progress_bar": "none", "media_dir": str(media_dir)}):
        result["fps"] = config.frame_rate
        scene = Probe()
        scene.render()
        result["duration"] = round(scene.renderer.time, 4)
    result["calls"] = calls
    return result


@pytest.fixture(scope="module")
def dry(tmp_path_factory):
    return _run(True, tmp_path_factory.mktemp("dry"))


def test_low_quality_runs_at_15_fps(dry):
    """The roadmap's frame clock is the low-quality frame rate."""
    assert dry["fps"] == 15


def test_dry_run_calls_updaters_on_every_frame(dry):
    times = [t for t, _ in dry["calls"]]
    frames = int(round(dry["duration"] * dry["fps"]))        # 1.4 s -> 21
    for k in range(frames):
        t = round(k / dry["fps"], 4)
        assert t in times, f"no updater call for frame {k} (t = {t})"
    # Between frames the updater is given one frame of time.
    assert round(1 / dry["fps"], 4) in {dt for _, dt in dry["calls"]}


def test_dry_run_leaves_updated_mobjects_in_the_right_place(dry):
    x, y, _ = dry["after_play"]
    assert (round(x, 6), round(y, 6)) == (3.0, 1.0)


def test_dry_run_matches_a_real_render(dry, tmp_path):
    real = _run(False, tmp_path)
    assert dry["calls"] == real["calls"]
    assert dry["duration"] == real["duration"]
