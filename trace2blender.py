"""
trace2blender.py — build an animated Blender scene from a PAM motion
trace produced by pam_trace.py.

Run inside Blender:
    blender --background --python trace2blender.py -- trace.json out.blend [options]
or with the standalone bpy module:
    python trace2blender.py trace.json out.blend [options]

Options:
    --fps N            frame rate (default 30)
    --res WxH          render resolution (default 1280x720)
    --tol T            max easing error (fraction of the move) accepted
                       when mapping a Manim rate function onto a native
                       Blender easing; otherwise the move is baked per
                       frame (default 0.015)
    --exact            bake every non-linear move per frame (no native
                       easing approximations at all)
    --locomotion MODE  "spline" (default): walk/run/carry cycles use a
                       C1 cubic spline through the keyframe poses, a
                       steady root, foot locking and hip bob.
                       "exact": per-keyframe Manim easing, still with
                       foot locking.
    --no-footlock      disable foot locking
    --bob S            hip-bob scale (default 1.0; 0 disables)
    --look LOOK        "eevee" (default): solid rounded figures, lights,
                       cast shadows on a floor and back wall (EEVEE);
                       "studio": the same figures with fast Workbench
                       shading; "flat": the original thin, unlit look
    --tilt DEG         camera tilt down toward the floor (default 8;
                       ignored by the flat look)
    --no-bubbles       leave out the speech bubbles
    --no-props         leave out props and scene objects (trace version 3)
    --hips F           male hip spread, as a fraction of PAM's (default
                       0.65; 1 keeps PAM's spread).  The tops of the legs
                       move in; the feet stay where they are.
    --skin A=#hex,...  skin color for the head, neck, arms and legs (the
                       chest, shoulders and hips keep the figure's color,
                       as clothing).  A cast entry's "skin" (or
                       style.skin_color) does the same from the screenplay.
    --shoes HEX        shoe color (default #4a3020, brown); --no-shoes for none
    --female A,B       draw these characters with a female chest (narrow
                       top, wide bottom); --male A,B the reverse.
    --bust             add a bust to female chests (off by default)
                       Otherwise the screenplay's "gender" is used, and a
                       "narrow" build counts as female.

Coordinate mapping: PAM/Manim (x right, y up) -> Blender (x right, z up),
characters live on the y = 0 plane, the camera looks along +y.

Works with Blender 3.x, 4.x and 5.x.  Trace version 1 (the original
probe) is still accepted; version 2 adds the hook data used for easing,
foot locking and visibility; version 3 adds props and scene objects.

Props: desks, tables and consoles (with their monitor), doors, chairs,
cellphones and the Governor dodecahedron get simple 3D models; any other
prop type is extruded from its 2D Manim outline.  Held props follow the
holding figure's hand(s) (or head/torso for pam_follows accessories),
floor-standing props are set on the floor, and a prop placed on a table
lies on its top.  The Governor spins (when its step asks for "spin"),
glows gold, flares word by word while it speaks, and dims to amber and
slows down in its low-power state.
"""
import json
import math
import os
import sys

import numpy as np

FPS = 30
BONE_R = 0.045       # bone tube radius, Manim units
JOINT_R = 0.07
CUT_NUDGE = 0.02     # frames between the two keys of a hard cut (Blender
                     # 5.x merges keys closer than 0.01 frame)

LEGS = (("lhip", "lknee", "lankle"), ("rhip", "rknee", "rankle"))
STRAIGHT = 0.985     # planted legs reach at most this fraction of full length
SOFT_IK = 0.96       # swinging legs ease into full extension from here
BOB = {"walk": 0.030, "carry_walk": 0.025, "side_carry_r_walk": 0.025,
       "squeeze_walk": 0.015, "run": 0.050}


# ═════════════════════════════════════════════════════════════════════════
#  Options
# ═════════════════════════════════════════════════════════════════════════

class Options:
    fps = FPS
    res = (1280, 720)
    tol = 0.015
    exact = False
    locomotion = "spline"
    footlock = True
    bob = 1.0
    look = "eevee"
    female = ()
    male = ()
    bust = False
    tilt = 8.0
    bubbles = True
    props = True
    hips = 0.65
    skin = {}
    shoes = "#4a3020"


def parse_args(argv):
    a = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    opt = Options()
    pos = []
    i = 0
    while i < len(a):
        k = a[i]
        if k == "--fps":
            opt.fps = int(a[i + 1]); i += 1
        elif k == "--res":
            w, h = a[i + 1].lower().split("x"); opt.res = (int(w), int(h)); i += 1
        elif k == "--tol":
            opt.tol = float(a[i + 1]); i += 1
        elif k == "--exact":
            opt.exact = True
        elif k == "--locomotion":
            opt.locomotion = a[i + 1]; i += 1
        elif k == "--no-footlock":
            opt.footlock = False
        elif k == "--bob":
            opt.bob = float(a[i + 1]); i += 1
        elif k == "--look":
            opt.look = a[i + 1]; i += 1
        elif k == "--tilt":
            opt.tilt = float(a[i + 1]); i += 1
        elif k == "--no-bubbles":
            opt.bubbles = False
        elif k == "--no-props":
            opt.props = False
        elif k == "--hips":
            opt.hips = float(a[i + 1]); i += 1
        elif k == "--skin":
            for item in a[i + 1].split(","):
                if "=" in item:
                    nm, hx = item.split("=", 1)
                    opt.skin[nm.strip()] = hx.strip()
            i += 1
        elif k == "--shoes":
            opt.shoes = a[i + 1]; i += 1
        elif k == "--no-shoes":
            opt.shoes = None
        elif k == "--bust":
            opt.bust = True
        elif k == "--female":
            opt.female = tuple(x for x in a[i + 1].split(",") if x); i += 1
        elif k == "--male":
            opt.male = tuple(x for x in a[i + 1].split(",") if x); i += 1
        else:
            pos.append(k)
        i += 1
    if not pos:
        sys.exit("usage: trace2blender.py trace.json [out.blend] [options]")
    return pos[0], (pos[1] if len(pos) > 1 else "pam_scene.blend"), opt


# ═════════════════════════════════════════════════════════════════════════
#  Rate functions (Manim -> Python)
# ═════════════════════════════════════════════════════════════════════════

def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _smooth(t, inflection=10.0):
    err = _sigmoid(-inflection / 2)
    return np.clip((_sigmoid(inflection * (t - 0.5)) - err) / (1 - 2 * err),
                   0, 1)


def _tabwp(t):
    a = 3.0
    return np.where(t < 1 / 3, _smooth(a * t),
                    np.where(t < 2 / 3, 1.0, _smooth(a - a * t)))


EXACT_RATES = {
    "linear": lambda t: t,
    "smooth": _smooth,
    "rush_from_start": lambda t: 1 - (1 - t) ** 2,
    "rush_into_start": lambda t: t ** 2,
    "slow_into": lambda t: np.sqrt(np.clip(1 - (1 - t) ** 2, 0, 1)),
    "there_and_back_with_pause": _tabwp,
    "there_and_back": lambda t: np.where(t < 0.5, _smooth(2 * t),
                                         _smooth(2 - 2 * t)),
    "double_smooth": lambda t: np.where(t < 0.5, 0.5 * _smooth(2 * t),
                                        0.5 * (1 + _smooth(2 * t - 1))),
    "rush_into": lambda t: 2 * _smooth(t / 2.0),
    "rush_from": lambda t: 2 * _smooth(t / 2.0 + 0.5) - 1,
}

GRID = np.linspace(0.0, 1.0, 65)


class Rate:
    """A Manim rate function, exact when known by name, else tabulated."""

    def __init__(self, name, samples=None):
        self.name = name
        fn = EXACT_RATES.get(name)
        if fn is None and name.rsplit("_", 1)[0] in EXACT_RATES \
                and name.rsplit("_", 1)[-1].isdigit():
            fn = EXACT_RATES[name.rsplit("_", 1)[0]]
        if fn is not None and samples is not None:
            # only trust the formula if it matches what was recorded
            if np.max(np.abs(np.asarray(fn(GRID), float)
                             - np.asarray(samples, float))) > 2e-3:
                fn = None
        self.table = (np.asarray(samples, float) if samples is not None
                      else np.asarray(EXACT_RATES.get(name, lambda t: t)(GRID),
                                      float))
        self.fn = fn

    def __call__(self, a):
        a = np.clip(np.asarray(a, float), 0.0, 1.0)
        if self.fn is not None:
            return np.asarray(self.fn(a), float)
        return np.interp(a, GRID, self.table)

    @property
    def end(self):
        return float(self(1.0))

    @property
    def monotone(self):
        d = np.diff(self(np.linspace(0, 1, 257)))
        return bool(np.all(d >= -1e-9))


# Penner easing curves as implemented by Blender (used to pick a native
# interpolation; every choice is verified against Blender's own fcurve
# evaluation before use).
def _penner():
    def io(f_in):
        def f(u):
            u = np.asarray(u, float)
            return np.where(u < 0.5, f_in(2 * u) / 2,
                            1 - f_in(2 - 2 * u) / 2)
        return f

    def out(f_in):
        return lambda u: 1 - f_in(1 - np.asarray(u, float))

    ins = {
        "SINE": lambda u: 1 - np.cos(u * np.pi / 2),
        "QUAD": lambda u: u ** 2,
        "CUBIC": lambda u: u ** 3,
        "QUART": lambda u: u ** 4,
        "QUINT": lambda u: u ** 5,
        "EXPO": lambda u: np.where(u <= 0, 0.0, 2.0 ** (10 * (u - 1))),
        "CIRC": lambda u: 1 - np.sqrt(np.clip(1 - u * u, 0, 1)),
    }
    cand = {("LINEAR", "AUTO"): lambda u: np.asarray(u, float)}
    for k, f in ins.items():
        cand[(k, "EASE_IN")] = f
        cand[(k, "EASE_OUT")] = out(f)
        cand[(k, "EASE_IN_OUT")] = io(f)
    return cand


PENNER = _penner()


def best_native(rate, tol):
    """(interpolation, easing, max_error) of the closest native easing,
    or None if no candidate is within *tol*."""
    if not rate.monotone or abs(rate.end - 1.0) > 1e-6 or abs(float(rate(0.0))) > 1e-6:
        return None
    u = np.linspace(0, 1, 401)
    r = rate(u)
    best = None
    for key, f in PENNER.items():
        e = float(np.max(np.abs(f(u) - r)))
        if best is None or e < best[2]:
            best = (key[0], key[1], e)
    return best if best[2] <= tol else None


# ═════════════════════════════════════════════════════════════════════════
#  Trace loading (v1 compatibility)
# ═════════════════════════════════════════════════════════════════════════

def load_trace(path):
    T = json.load(open(path))
    if T.get("trace_version", 1) >= 2:
        T.setdefault("prop_objects", [])       # added in trace version 3
        return T
    # ── version 1: snapshots at play/wait boundaries -> linear pieces ──
    S = T["samples"]
    tracks, vis, initial = {}, {}, {}
    camera, last_cam = [], None
    prev = {}
    for i, s in enumerate(S):
        for name, joints in s["figs"].items():
            w = {j: v for j, v in joints.items() if not j.startswith("_")}
            on = joints.get("_opacity", 1) > 0.01
            tracks.setdefault(name, [])
            vis.setdefault(name, [])
            if not vis[name] or vis[name][-1][1] != on:
                t = s["t"]
                if on and s["kind"] == "play" and i > 0:
                    t = S[i - 1]["t"]      # appeared during this play
                vis[name].append([t, on, 1.0 if on else 0.0])
            if name in prev:
                t0, w0 = prev[name]
                if w0 != w:
                    tracks[name].append({"t0": t0, "t1": s["t"],
                                         "kind": "play", "source": "play",
                                         "rate": "linear",
                                         "from": w0, "to": w})
            else:
                initial[name] = w
            prev[name] = (s["t"], w)
        cam = s["cam"]
        if last_cam is not None and cam != last_cam[1]:
            camera.append({"t0": last_cam[0], "t1": s["t"], "rate": "linear",
                           "from": last_cam[1], "to": cam})
        last_cam = (s["t"], cam)
    cast = {}
    for name, info in T["cast"].items():
        info = dict(info)
        info.setdefault("joints", list(initial.get(name, {}).keys()))
        cast[name] = info
    return {"trace_version": 1, "duration": S[-1]["t"],
            "frame": {"width": S[0]["cam"]["width"]},
            "rate_funcs": {}, "cast": cast, "tracks": tracks,
            "visibility": vis, "initial": initial,
            "camera_initial": S[0]["cam"], "camera": camera,
            "actions": [], "props": [], "prop_objects": []}


# ═════════════════════════════════════════════════════════════════════════
#  Motion evaluation (pure numpy; no bpy needed)
# ═════════════════════════════════════════════════════════════════════════

def _arr(d, joints):
    return np.array([d[j] for j in joints], float)


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _hermite_tangents(ts, ps):
    """Monotone (Fritsch-Carlson-style) tangents: average of neighboring
    secants, zero at local extrema and at both ends -- the same shape
    rule as Blender's auto-clamped Bezier handles."""
    n = len(ts)
    m = np.zeros_like(ps)
    if n < 3:
        return m
    d = np.diff(ps, axis=0) / np.diff(ts)[:, None, None]
    for k in range(1, n - 1):
        a, b = d[k - 1], d[k]
        avg = 0.5 * (a + b)
        same = (a * b) > 0
        m[k] = np.where(same, avg, 0.0)
        # clamp to avoid overshoot (Fritsch-Carlson limit 3x secant)
        lim = 3 * np.minimum(np.abs(a), np.abs(b))
        m[k] = np.clip(m[k], -lim, lim)
    return m


def _hermite_eval(ts, ps, ms, t):
    """Evaluate a cubic Hermite spline (keys ts, values ps (K,J,2),
    tangents ms) at times t (N,) -> (N,J,2)."""
    t = np.clip(t, ts[0], ts[-1])
    k = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2)
    h = (ts[k + 1] - ts[k])
    s = np.where(h > 0, (t - ts[k]) / np.where(h > 0, h, 1), 0.0)
    s2, s3 = s * s, s * s * s
    h00 = 2 * s3 - 3 * s2 + 1
    h10 = s3 - 2 * s2 + s
    h01 = -2 * s3 + 3 * s2
    h11 = s3 - s2
    H = lambda c: c[:, None, None]
    return (H(h00) * ps[k] + H(h10 * h) * ms[k]
            + H(h01) * ps[k + 1] + H(h11 * h) * ms[k + 1])


def piece_eval(piece, joints, rate, t):
    """World joints (N,J,2) of a simple piece at times t."""
    a0 = _arr(piece["from"], joints)
    a1 = _arr(piece["to"], joints)
    dur = piece["t1"] - piece["t0"]
    al = np.clip((t - piece["t0"]) / dur, 0, 1) if dur > 0 else np.ones_like(t)
    r = rate(al)
    if "target" in piece:
        tg = np.array([piece["target"].get(j, piece["to"][j]) for j in joints],
                      float)
    elif abs(rate.end - 1.0) > 1e-6 and abs(rate.end) > 1e-6:
        tg = a0 + (a1 - a0) / rate.end
    else:
        tg = a1
    return a0[None] + r[:, None, None] * (tg - a0)[None]


class LocoRun:
    """A contiguous walk/run/carry sequence of one character: a spline
    through the keyframe poses, a steady root, foot locking with
    two-bone leg IK, and a subtle hip bob."""

    def __init__(self, pieces, joints, rates, prev_contacts, opt):
        self.p = pieces
        self.J = joints
        self.ji = {j: i for i, j in enumerate(joints)}
        self.opt = opt
        self.t0 = pieces[0]["t0"]
        self.t1 = pieces[-1]["t1"]
        ts = [pieces[0]["t0"]] + [p["t1"] for p in pieces]
        self.ts = np.array(ts, float)
        W = [_arr(pieces[0]["from"], joints)] + [_arr(p["to"], joints)
                                                  for p in pieces]
        self.W = np.array(W)                                   # (K+1,J,2)
        O = [pieces[0].get("offset0") or pieces[0]["offset"]] + \
            [p["offset"] for p in pieces]
        self.O = np.array(O, float)[:, None, :]                # (K+1,1,2)
        self.L = self.W - self.O                               # rotated local
        self.rates = rates
        gaits = [p.get("gait") for p in pieces if p.get("gait")]
        self.gait = max(set(gaits), key=gaits.count) if gaits else None
        # contacts at every boundary
        C = [set(prev_contacts) if prev_contacts is not None
             else self._geom_contacts(0)]
        for k, p in enumerate(pieces, start=1):
            c = p.get("contacts")
            C.append(set(c) if c is not None else self._geom_contacts(k))
        self.C = C
        self._reground()
        self._prepare()

    def _reground(self):
        """PAM scales a figure about a *live* joint (by default its
        lankle).  When that ankle lifts in a walk/run keyframe, the whole
        scaled body rises with it -- a hop of (1 - scale) x lift that the
        Manim render shows too.  Re-seat each keyframe so its planted
        feet stay on the run's ground line; keyframes with no planted
        foot (run flight) take the interpolated correction of their
        neighbors.  The run's first and last keyframes are untouched, so
        the run still starts and ends exactly where Manim does."""
        K = len(self.p)
        self.shift = np.zeros(K + 1)
        ank = [a for _, _, a in LEGS if a in self.ji]
        if not ank:
            return
        c0 = [a for a in ank if a in self.C[0]] or ank
        ref = min(self.W[0, self.ji[a], 1] for a in c0)
        known = {}
        for k in range(K + 1):
            ck = [a for a in ank if a in self.C[k]]
            if ck:
                known[k] = ref - min(self.W[k, self.ji[a], 1] for a in ck)
        known[0] = 0.0
        known[K] = 0.0
        ks = np.array(sorted(known))
        self.shift = np.interp(np.arange(K + 1), ks,
                               np.array([known[k] for k in ks]))

    def _geom_contacts(self, k):
        out = set()
        ys = {a: self.L[k, self.ji[a], 1] for _, _, a in LEGS if a in self.ji}
        if ys:
            lo = min(ys.values())
            out = {a for a, y in ys.items() if y < lo + 0.03}
        return out

    # ── raw (pre-locking) motion ────────────────────────────────────────
    def raw(self, t):
        X = self._raw(t)
        X[:, :, 1] += _hermite_eval(self.ts, self.shift[:, None, None],
                                    self.mS, t)[:, :, 0]
        return X

    def _raw(self, t):
        if self.opt.locomotion == "exact":
            out = np.empty((len(t), len(self.J), 2))
            k = np.clip(np.searchsorted(self.ts, t, side="right") - 1,
                        0, len(self.p) - 1)
            for i, p in enumerate(self.p):
                sel = k == i
                if np.any(sel):
                    out[sel] = piece_eval(p, self.J, self.rates[p["rate"]],
                                          t[sel])
            return out
        return (_hermite_eval(self.ts, self.L, self.mL, t)
                + _hermite_eval(self.ts, self.O, self.mO, t))

    def _prepare(self):
        self.mL = _hermite_tangents(self.ts, self.L)
        self.mO = _hermite_tangents(self.ts, self.O)
        self.mS = _hermite_tangents(self.ts, self.shift[:, None, None])
        # lock intervals per ankle
        self.locks = {}
        self.ground = None
        self.has_legs = all(j in self.ji for leg in LEGS for j in leg)
        if not self.has_legs:
            return
        K = len(self.p)
        ji = self.ji
        legs = [np.linalg.norm(self.L[:, ji[k]] - self.L[:, ji[h]], axis=1)
                + np.linalg.norm(self.L[:, ji[a]] - self.L[:, ji[k]], axis=1)
                for h, k, a in LEGS]
        self.leg = float(np.mean(legs))
        self.cap = 0.06 * self.leg          # max hip drop for reaching
        # Which way each knee bends, decided once per run from the
        # keyframes (a per-frame choice could flip on near-straight legs).
        self.knee_side = {}
        for hip, knee, ank in LEGS:
            v1 = self.L[:, ji[ank]] - self.L[:, ji[hip]]
            v2 = self.L[:, ji[knee]] - self.L[:, ji[hip]]
            cr = float(np.sum(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]))
            self.knee_side[hip] = 1.0 if cr >= 0 else -1.0
        if not self.opt.footlock:
            return
        for hip, knee, ank in LEGS:
            ivs, cur = [], None
            for k in range(1, K + 1):
                on = ank in self.C[k - 1] and ank in self.C[k]
                if on:
                    cur = [k - 1, k] if cur is None else [cur[0], k]
                elif cur is not None:
                    ivs.append(cur); cur = None
            if cur is not None:
                ivs.append(cur)
            locks = []
            for a, b in ivs:
                ta, tb = self.ts[a], self.ts[b]
                ai = self.ji[ank]
                if a == 0:
                    pin = self.W[0, ai].copy()
                elif b == K:
                    pin = self.W[K, ai].copy()
                else:
                    tt = np.linspace(ta, tb, 33)
                    pin = self.raw(tt)[:, ai].mean(axis=0)
                # A foot that stays put from the run's start (or lands for
                # the final settle) can be left far behind (or reach far
                # ahead) when the root travels farther than the legs can
                # stride.  Instead of stretching or sliding, release it
                # (toe-off) once it is out of reach, or land it once it
                # comes into reach; the freed time becomes swing.
                if (a == 0) != (b == K):
                    tt = np.linspace(ta, tb, 61)
                    ok = self._reachable(hip, knee, ank, pin, tt)
                    if a == 0 and not ok.all():
                        i = int(np.argmin(ok))
                        tb = tt[max(i - 1, 1)]
                    elif b == K and not ok.all():
                        i = len(ok) - 1 - int(np.argmin(ok[::-1]))
                        ta = tt[min(i + 1, len(tt) - 2)]
                locks.append((ta, tb, pin))
            self.locks[ank] = locks
        pins = [pin[1] for v in self.locks.values() for (_, _, pin) in v]
        self.ground = min(pins) if pins else None

    def _reachable(self, hip, knee, ank, pin, tt):
        X = self.raw(tt)
        H, Kn, A = X[:, self.ji[hip]], X[:, self.ji[knee]], X[:, self.ji[ank]]
        L = np.linalg.norm(Kn - H, axis=1) + np.linalg.norm(A - Kn, axis=1)
        dx = H[:, 0] - pin[0]
        need = H[:, 1] - (pin[1] + np.sqrt(np.clip(L * L - dx * dx, 0, None)))
        return (np.abs(dx) < L) & (need <= self.cap)

    # ── final motion ────────────────────────────────────────────────────
    def _targets(self, t, X):
        """Ankle targets (planted pins, eased swings) and lock flags."""
        ji = self.ji
        # ankle targets and lock flags
        tgt, locked = {}, {}
        for _, _, ank in LEGS:
            ai = ji[ank]
            A = X[:, ai].copy()
            lk = np.zeros(len(t), bool)
            locks = self.locks.get(ank, [])
            if locks:
                corr = np.zeros((len(t), 2))
                # boundaries: (time, correction) sequence incl. run ends
                for (ta, tb, pin) in locks:
                    sel = (t >= ta) & (t <= tb)
                    A[sel] = pin
                    lk |= sel
                # blend corrections in the gaps between locks
                pts = []
                for (ta, tb, pin) in locks:
                    ca = pin - self.raw(np.array([ta]))[0, ai]
                    cb = pin - self.raw(np.array([tb]))[0, ai]
                    pts.append((ta, tb, ca, cb))
                edges = [(self.t0, np.zeros(2))]
                for (ta, tb, ca, cb) in pts:
                    edges.append((ta, ca))
                    edges.append((tb, cb))
                edges.append((self.t1, np.zeros(2)))
                for i in range(0, len(edges) - 1, 2):
                    (ga, ca), (gb, cb) = edges[i], edges[i + 1]
                    sel = (t > ga) & (t < gb) & ~lk
                    if np.any(sel) and gb > ga:
                        w = _smoothstep((t[sel] - ga) / (gb - ga))[:, None]
                        corr[sel] = (1 - w) * ca + w * cb
                A = np.where(lk[:, None], A, A + corr)
                # Swing between two plants: travel from pin to pin with
                # zero speed at lift-off and touch-down (smoothstep), and
                # keep the keyframes' own swing shape (their deviation from
                # a straight chord), faded in and out with sin(pi v) so it
                # adds no speed at the ends either.  A minimum clearance
                # arc keeps an early-released foot off the ground.
                for i in range(1, len(locks)):
                    ga, gb = locks[i - 1][1], locks[i][0]
                    pa, pb = locks[i - 1][2], locks[i][2]
                    sel = (t > ga) & (t < gb) & ~lk
                    if not np.any(sel) or gb <= ga:
                        continue
                    v = (t[sel] - ga) / (gb - ga)
                    ra = self.raw(np.array([ga]))[0, ai]
                    rb = self.raw(np.array([gb]))[0, ai]
                    dev = X[sel, ai] - (ra + (rb - ra) * v[:, None])
                    A[sel] = (pa + (pb - pa) * _smoothstep(v)[:, None]
                              + dev * np.sin(np.pi * v)[:, None])
                    if self.ground is not None:
                        A[sel, 1] = np.maximum(
                            A[sel, 1],
                            self.ground + 0.10 * self.leg * np.sin(np.pi * v))
            if self.ground is not None:
                A[:, 1] = np.maximum(A[:, 1], np.where(lk, A[:, 1], self.ground))
            tgt[ank], locked[ank] = A, lk
        return tgt, locked

    def _drop_raw(self, t, X, tgt, locked):
        """Hip drop needed to reach the planted feet, combined with the
        hip bob (before temporal smoothing)."""
        ji = self.ji
        r_in = max(self.ts[1] - self.ts[0], 1e-3)
        r_out = max(self.ts[-1] - self.ts[-2], 1e-3)
        env = np.minimum(_smoothstep((t - self.t0) / r_in),
                         _smoothstep((self.t1 - t) / r_out))
        drop_ik = np.zeros(len(t))
        lens = {}
        for hip, knee, ank in LEGS:
            H, Kn, A0 = X[:, ji[hip]], X[:, ji[knee]], X[:, ji[ank]]
            l1 = np.linalg.norm(Kn - H, axis=1)
            l2 = np.linalg.norm(A0 - Kn, axis=1)
            lens[hip] = (l1, l2)
            L = (l1 + l2) * STRAIGHT     # keep planted knees slightly bent
            A = tgt[ank]
            dx = H[:, 0] - A[:, 0]
            reach = np.sqrt(np.clip(L * L - dx * dx, 0, None))
            need = H[:, 1] - (A[:, 1] + reach)
            need = np.where(locked[ank], np.maximum(need, 0), 0)
            drop_ik = np.maximum(drop_ik, need)
        drop_ik = np.minimum(drop_ik, self.cap)

        # hip bob
        amp = BOB.get(self.gait, 0.0) * self.opt.bob
        bob = np.zeros(len(t))
        if amp > 0:
            st = []
            for v in self.locks.values():
                st += [(ta, tb) for (ta, tb, _) in v]
            st.sort()
            in_stance = np.zeros(len(t), bool)
            for ta, tb in st:
                sel = (t >= ta) & (t <= tb)
                u = (t[sel] - ta) / max(tb - ta, 1e-6)
                if self.gait == "run":
                    val = amp * np.sin(np.pi * u)               # compress
                else:
                    val = amp * (1 - np.sin(np.pi * u))         # vault
                bob[sel] = np.where(in_stance[sel], np.maximum(bob[sel], val), val)
                in_stance |= sel
            if self.gait == "run":
                # flight phases rise a little
                gaps = [(st[i][1], st[i + 1][0]) for i in range(len(st) - 1)
                        if st[i + 1][0] > st[i][1]]
                for ga, gb in gaps:
                    sel = (t > ga) & (t < gb) & ~in_stance
                    v = (t[sel] - ga) / (gb - ga)
                    bob[sel] = -0.6 * amp * np.sin(np.pi * v)
            bob *= env
        return np.maximum(drop_ik, bob) if amp > 0 else drop_ik

    def _drop(self, t):
        """Smoothed hip drop.  The raw curve has kinks where feet plant
        and lift (and is a max of two curves); it is dilated by 60 ms (so
        the smoothed curve still covers what the planted feet need) and
        then Gaussian-smoothed (sigma 30 ms), and tapered to zero at the
        run's ends so it meets the neighboring Manim poses exactly."""
        if getattr(self, "_drop_grid", None) is None:
            dt = 1.0 / 240.0
            n = max(int(math.ceil((self.t1 - self.t0) / dt)) + 1, 2)
            tg = np.linspace(self.t0, self.t1, n)
            Xg = self.raw(tg)
            tgt, locked = self._targets(tg, Xg)
            d = self._drop_raw(tg, Xg, tgt, locked)
            step = (self.t1 - self.t0) / (n - 1)
            r = max(int(round(0.06 / step)), 1)
            pad = np.pad(d, r, mode="edge")
            win = np.lib.stride_tricks.sliding_window_view(pad, 2 * r + 1)
            d = win.max(axis=1)
            sig = max(0.03 / step, 1.0)
            k = np.arange(-int(3 * sig), int(3 * sig) + 1)
            g = np.exp(-0.5 * (k / sig) ** 2)
            g /= g.sum()
            d = np.convolve(np.pad(d, len(k) // 2, mode="edge"), g, mode="valid")
            taper = np.minimum(_smoothstep((tg - self.t0) / 0.1),
                               _smoothstep((self.t1 - tg) / 0.1))
            self._drop_grid = (tg, d * taper)
        tg, d = self._drop_grid
        return np.interp(t, tg, d)

    # ── final motion ────────────────────────────────────────────────────
    def eval(self, t):
        t = np.asarray(t, float)
        X = self.raw(t)
        if not self.has_legs:
            return X
        ji = self.ji
        tgt, locked = self._targets(t, X)
        lens = {}
        for hip, knee, ank in LEGS:
            lens[hip] = (np.linalg.norm(X[:, ji[knee]] - X[:, ji[hip]], axis=1),
                         np.linalg.norm(X[:, ji[ank]] - X[:, ji[knee]], axis=1))
        drop = self._drop(t)

        Y = X.copy()
        lower = {ji[k] for _, k, _ in LEGS} | {ji[a] for _, _, a in LEGS}
        for j in range(len(self.J)):
            if j not in lower:
                Y[:, j, 1] -= drop

        # two-bone IK per leg (knee bends to the same side as in the pose)
        for hip, knee, ank in LEGS:
            H = Y[:, ji[hip]]
            A = tgt[ank]
            l1, l2 = lens[hip]
            D = A - H
            d = np.linalg.norm(D, axis=1)
            dmax = (l1 + l2) * (1 - 1e-9)
            dmin = np.abs(l1 - l2) + 1e-6
            # A planted foot that is out of reach even after the hip drop
            # rises in place (heel-off) instead of sliding: keep its x and
            # put it on the leg-length circle below the hip.
            lk = locked[ank]
            far = lk & (d > dmax)
            if np.any(far):
                dx = A[far, 0] - H[far, 0]
                ok = np.abs(dx) < dmax[far]
                yy = H[far, 1] - np.sqrt(np.clip(dmax[far] ** 2 - dx ** 2, 0, None))
                A = A.copy()
                A[np.flatnonzero(far)[ok], 1] = yy[ok]
                D = A - H
                d = np.linalg.norm(D, axis=1)
            dc = np.clip(d, dmin, dmax)
            # soft IK for swinging legs: approach full extension smoothly
            # (an exact solve snaps the knee as the leg straightens)
            ds = dmax * SOFT_IK
            soft = ~lk & (d > ds)
            if np.any(soft):
                w = dmax[soft] - ds[soft]
                dc[soft] = ds[soft] + w * (1 - np.exp(-(d[soft] - ds[soft]) / w))
            u = D / np.maximum(d, 1e-9)[:, None]
            A = H + u * dc[:, None]                       # reachable ankle
            cosa = np.clip((l1 ** 2 + dc ** 2 - l2 ** 2) / (2 * l1 * dc), -1, 1)
            sina = np.sqrt(1 - cosa ** 2)
            perp = np.stack([-u[:, 1], u[:, 0]], axis=1) * self.knee_side[hip]
            Kn = H + l1[:, None] * (cosa[:, None] * u + sina[:, None] * perp)
            Y[:, ji[knee]] = Kn
            Y[:, ji[ank]] = A
        return Y


def build_timeline(name, T, rates, opt):
    """Return [(kind, obj)] for one character: ("piece", p) or
    ("run", LocoRun)."""
    joints = T["cast"][name]["joints"]
    tr = sorted(T["tracks"].get(name, []), key=lambda p: (p["t0"], p["t1"]))
    out = []
    i = 0
    prev_contacts = None
    while i < len(tr):
        p = tr[i]
        if p.get("gait") and "local" in p and "offset" in p \
                and p["kind"] != "cut":
            j = i
            while j + 1 < len(tr):
                q = tr[j + 1]
                contiguous = abs(q["t0"] - tr[j]["t1"]) < 1e-3 \
                    and q["kind"] != "cut" and "local" in q and "offset" in q
                if not contiguous:
                    break
                if q.get("gait"):
                    j += 1
                    continue
                # one trailing settle piece (no root motion)
                if np.allclose(q["offset"], tr[j]["offset"], atol=1e-6) \
                        and q.get("view") == tr[j].get("view"):
                    j += 1
                break
            run = tr[i:j + 1]
            if sum(1 for q in run if q.get("gait")) >= 2:
                out.append(("run", LocoRun(run, joints, rates, prev_contacts,
                                           opt)))
                prev_contacts = run[-1].get("contacts")
                i = j + 1
                continue
        out.append(("piece", p))
        if p.get("contacts") is not None or p.get("pose"):
            prev_contacts = p.get("contacts")
        i += 1
    return out


def sample_character(name, T, rates, opt, frames):
    """Evaluate a character's world joints at the given frames (used by
    the verification tools; Blender itself only sees keyframes)."""
    joints = T["cast"][name]["joints"]
    t = (np.asarray(frames, float) - 1) / opt.fps
    X = np.repeat(_arr(T["initial"][name], joints)[None], len(t), axis=0)
    for kind, obj in build_timeline(name, T, rates, opt):
        if kind == "run":
            sel = (t >= obj.t0) & (t <= obj.t1)
            if np.any(sel):
                X[sel] = obj.eval(t[sel])
            X[t > obj.t1] = obj.W[-1]
        else:
            p = obj
            sel = (t >= p["t0"]) & (t <= p["t1"])
            if np.any(sel) and p["t1"] > p["t0"]:
                X[sel] = piece_eval(p, joints, rates[p["rate"]], t[sel])
            X[t > p["t1"]] = _arr(p["to"], joints)
            if p["t1"] <= p["t0"]:
                X[t >= p["t0"]] = _arr(p["to"], joints)
    return X


# ═════════════════════════════════════════════════════════════════════════
#  Keyframe assembly
# ═════════════════════════════════════════════════════════════════════════

class KeyList:
    """Keys shared by all channels of one animated thing.  values are
    (n_channels,) arrays; spec is the interpolation of the segment that
    *starts* at this key: ("LINEAR"|"CONSTANT"|<Penner>, easing)."""

    def __init__(self, fps):
        self.fps = fps
        self.f, self.v, self.spec = [], [], []

    def frame(self, t):
        return 1.0 + t * self.fps

    def add(self, t, vals, spec=("LINEAR", "AUTO")):
        f = self.frame(t)
        vals = np.asarray(vals, float).ravel()
        if self.f and f <= self.f[-1] + 1e-6:
            if np.allclose(self.v[-1], vals, atol=1e-6):
                self.spec[-1] = spec
                return
            # hard cut: hold the old value, jump just after
            self.spec[-1] = ("CONSTANT", "AUTO")
            f = self.f[-1] + CUT_NUDGE
        self.f.append(f)
        self.v.append(vals)
        self.spec.append(spec)


def assemble_character(name, T, rates, opt, native):
    joints = T["cast"][name]["joints"]
    keys = KeyList(opt.fps)
    keys.add(0.0, _arr(T["initial"][name], joints))
    nbake = 0
    for kind, obj in build_timeline(name, T, rates, opt):
        if kind == "run":
            ts = _inner_times(obj.t0, obj.t1, opt.fps)
            tt = np.concatenate([[obj.t0], ts, [obj.t1]])
            Y = obj.eval(tt)
            for i, t in enumerate(tt):
                keys.add(t, Y[i])
            nbake += len(tt)
            continue
        p = obj
        a0 = _arr(p["from"], joints)
        a1 = _arr(p["to"], joints)
        if p["kind"] == "cut" or p["t1"] <= p["t0"]:
            keys.add(p["t0"], a0)
            keys.add(p["t0"], a1)
            continue
        r = rates[p["rate"]]
        nat = None if (opt.exact and p["rate"] != "linear") else native.get(p["rate"])
        if "target" in p:
            nat = None
        if nat is not None:
            keys.add(p["t0"], a0, (nat[0], nat[1]))
            keys.add(p["t1"], a1)
        else:
            ts = _inner_times(p["t0"], p["t1"], opt.fps)
            tt = np.concatenate([[p["t0"]], ts, [p["t1"]]])
            Y = piece_eval(p, joints, r, tt)
            Y[-1] = a1
            for i, t in enumerate(tt):
                keys.add(t, Y[i])
            nbake += len(tt)
    return keys, nbake


def _inner_times(t0, t1, fps):
    f0, f1 = 1 + t0 * fps, 1 + t1 * fps
    fr = np.arange(math.floor(f0) + 1, math.ceil(f1))
    fr = fr[(fr > f0 + 1e-6) & (fr < f1 - 1e-6)]
    return (fr - 1) / fps


def assemble_camera(T, rates, opt, native):
    keys = KeyList(opt.fps)
    c0 = T.get("camera_initial") or (T["camera"][0]["from"] if T["camera"]
                                     else {"center": [0, 0],
                                           "width": T["frame"]["width"]})
    v = lambda c: [c["center"][0], c["center"][1], c["width"]]
    keys.add(0.0, v(c0))
    for p in T["camera"]:
        a0, a1 = np.array(v(p["from"])), np.array(v(p["to"]))
        if p["t1"] <= p["t0"]:
            keys.add(p["t0"], a0); keys.add(p["t0"], a1)
            continue
        nat = None if (opt.exact and p["rate"] != "linear") else native.get(p["rate"])
        if nat is not None:
            keys.add(p["t0"], a0, (nat[0], nat[1])); keys.add(p["t1"], a1)
        else:
            r = rates[p["rate"]]
            ts = _inner_times(p["t0"], p["t1"], opt.fps)
            tt = np.concatenate([[p["t0"]], ts, [p["t1"]]])
            al = (tt - p["t0"]) / (p["t1"] - p["t0"])
            rr = r(al)
            if abs(r.end - 1) > 1e-6 and abs(r.end) > 1e-6:
                rr = rr / r.end
            for t, x in zip(tt, rr):
                keys.add(t, a0 + x * (a1 - a0))
    return keys


def load_rates(T):
    rates = {n: Rate(n, s) for n, s in T.get("rate_funcs", {}).items()}
    rates.setdefault("linear", Rate("linear"))
    for tr in T["tracks"].values():
        for p in tr:
            rates.setdefault(p["rate"], Rate(p["rate"]))
    for p in T.get("camera", []):
        rates.setdefault(p["rate"], Rate(p["rate"]))
    return rates


# ═════════════════════════════════════════════════════════════════════════
#  Blender side
# ═════════════════════════════════════════════════════════════════════════

def _lin(c):
    """sRGB component -> scene-linear (Blender colors are linear)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h):
    h = h.lstrip("#")[:6]
    return tuple(_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (1.0,)


def _fcurves(act):
    """Blender 4.4+/5.x use layered actions; older use act.fcurves."""
    if hasattr(act, "fcurves") and act.fcurves is not None:
        try:
            return list(act.fcurves)
        except Exception:
            pass
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def _id_fcurves(idblock):
    """FCurves animating *idblock*.  Blender 4.4+ may share one layered
    action between several IDs (e.g. a camera object and its camera
    data), each with its own slot, so look in that ID's slot first."""
    ad = idblock.animation_data
    act = ad.action
    slot = getattr(ad, "action_slot", None)
    if slot is not None and getattr(act, "layers", None):
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                cb = None
                if hasattr(strip, "channelbag"):
                    try:
                        cb = strip.channelbag(slot)
                    except Exception:
                        cb = None
                if cb is not None:
                    out += list(cb.fcurves)
        if out:
            return out
    return _fcurves(act)


def _fcurve(idblock, path, index):
    """Create (via keyframe_insert, which works on 3.x-5.x) and return the
    fcurve animating idblock.path[index]."""
    prop = idblock.bl_rna.properties.get(path)
    if prop is not None and not getattr(prop, "is_array", False):
        idblock.keyframe_insert(path, frame=0.0)        # scalar property
        index = 0
    else:
        try:
            idblock.keyframe_insert(path, index=index, frame=0.0)
        except TypeError:
            # nested scalar, e.g. 'constraints["hold"].influence'
            idblock.keyframe_insert(path, frame=0.0)
            index = 0
    for fc in _id_fcurves(idblock):
        if fc.data_path == path and fc.array_index == index:
            fc.keyframe_points.clear() if hasattr(fc.keyframe_points, "clear") \
                else [fc.keyframe_points.remove(k) for k in
                      list(fc.keyframe_points)[::-1]]
            return fc
    raise RuntimeError(f"fcurve {path}[{index}] not found")


_INTERP_IDS = {}
_EASING_IDS = {}


def _enum_ids(bpy):
    if _INTERP_IDS:
        return
    for prop, table in (("interpolation", _INTERP_IDS), ("easing", _EASING_IDS)):
        items = bpy.types.Keyframe.bl_rna.properties[prop].enum_items
        for it in items:
            table[it.identifier] = it.value


def write_fcurve(bpy, fc, frames, values, specs):
    n = len(frames)
    kp = fc.keyframe_points
    kp.add(n)
    co = np.empty(2 * n, np.float32)
    co[0::2] = frames
    co[1::2] = values
    kp.foreach_set("co", co)
    interp = [s[0] for s in specs]
    eas = [s[1] for s in specs]
    try:
        kp.foreach_set("interpolation",
                       np.array([_INTERP_IDS[i] for i in interp], np.int32))
        kp.foreach_set("easing",
                       np.array([_EASING_IDS[e] for e in eas], np.int32))
    except Exception:
        for k, i, e in zip(kp, interp, eas):
            k.interpolation = i
            k.easing = e
    # flat handles at the keys (only BEZIER keys would use them)
    try:
        kp.foreach_set("handle_left", co)
        kp.foreach_set("handle_right", co)
    except Exception:
        pass
    fc.update()


def apply_keys(bpy, idblock, path, chans, keys):
    """chans: list of (array_index, column, transform)."""
    if not keys.f:
        return
    F = np.array(keys.f)
    V = np.array(keys.v)
    for index, col, tf in chans:
        fc = _fcurve(idblock, path, index)
        write_fcurve(bpy, fc, F, tf(V[:, col]), keys.spec)


def verify_native(bpy, rates, opt):
    """Pick a native Blender easing for each rate function and verify it
    against Blender's own fcurve evaluation."""
    _enum_ids(bpy)
    native = {}
    ob = bpy.data.objects.new("_ease_probe", None)
    bpy.context.scene.collection.objects.link(ob)
    for name, r in rates.items():
        if name == "linear":
            cand = ("LINEAR", "AUTO", 0.0)
        else:
            cand = best_native(r, opt.tol)
        if cand is None:
            continue
        ob.animation_data_clear()
        fc = _fcurve(ob, "location", 0)
        write_fcurve(bpy, fc, np.array([1.0, 101.0]), np.array([0.0, 1.0]),
                     [(cand[0], cand[1]), ("LINEAR", "AUTO")])
        u = np.linspace(0, 1, 101)
        got = np.array([fc.evaluate(1 + 100 * x) for x in u])
        err = float(np.max(np.abs(got - r(u))))
        if err <= max(opt.tol, 1e-4) + 1e-4:
            native[name] = (cand[0], cand[1], err)
    bpy.data.objects.remove(ob)
    return native


# ── look: materials, meshes, stage, bubbles ─────────────────────────────

ENGINE_EEVEE = ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE")   # 4.2-4.4 / 3.x, 5.x
CAM_DIST = 20.0
TORSO_JOINTS = {"neck", "torso", "torso_left", "torso_right"}
REF_HEIGHT = 5.1          # head-to-ankle height of a default front-view figure
LIMB_R, TORSO_R, NECK_R, HEAD_R = 0.20, 0.15, 0.09, 0.50
SHOULDER_R = 2 * TORSO_R  # neck-to-shoulder bars
INNER_JOINTS = {"torso", "torso_left", "torso_right"}   # inside the chest
CLOTHED_JOINTS = {"lshoulder", "rshoulder", "lhip", "rhip"}
SHOE_L, SHOE_W, SHOE_H = 0.85, 0.50, 0.34    # shoe size (times figure scale)
SHOE_FWD = 0.22                              # toe-ward offset of its center
HINGE_SCALE = 1.35        # knee/elbow balls this much wider than the limb
HINGES = {"lknee", "rknee", "lelbow", "relbow"}
CHEST_CORNERS = ("lshoulder", "rshoulder", "rhip", "lhip")
CHEST_DEPTH = 0.36        # front-to-back thickness of the chest slab
CHEST_PAD = 0.24          # extra width, so side views still show a body
CHEST_GRID = 8            # chest surface subdivisions (for the bust)
FEMALE_TOP = 0.45         # female chest: top width relative to the shoulders
FEMALE_FLARE = 1.6        # female chest: bottom at least this x the top
BUST_R = 0.20             # female chest: bust radius (times figure scale)
BUST_U, BUST_V = 0.27, 0.30   # bust position across / down the chest
FONT_PATHS = (
    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
    "/Library/Fonts/Courier New Bold.ttf",
    "C:/Windows/Fonts/courbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
)


def _socket(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def material(bpy, name, color, roughness=0.35, emission=False):
    """A Principled material (or an unlit emission material for bubbles).
    diffuse_color is set too, so Workbench looks shows the same color."""
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    if bpy.app.version < (5, 0, 0):              # always on in Blender 5+
        m.use_nodes = True
    nt = getattr(m, "node_tree", None)
    if nt is None:
        return m
    try:
        if emission:
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = color
            em.inputs["Strength"].default_value = 1.0
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        else:
            b = nt.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = color
            b.inputs["Roughness"].default_value = roughness
            sp = _socket(b, "Specular IOR Level", "Specular")
            if sp is not None:
                sp.default_value = 0.5
    except Exception as exc:
        print("material setup:", exc)
    m.roughness = roughness
    return m


def _shade_smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


def key_visibility(objs, seq, fps):
    """Key hide_render / hide_viewport on *objs* at the (t, visible)
    changes in *seq*, with CONSTANT interpolation.  (Boolean fcurves
    default to Bezier; Blender 5.x evaluates them as discrete steps,
    but 4.x truncates the interpolated value, so a prop or bubble keyed
    hidden ... visible shows up early.)"""
    for o in objs:
        for t, on in seq:
            f = 1 + t * fps
            o.hide_render = not on
            o.hide_viewport = not on
            o.keyframe_insert("hide_render", frame=f)
            o.keyframe_insert("hide_viewport", frame=f)
        if o.animation_data and o.animation_data.action:
            for fc in _id_fcurves(o):
                if fc.data_path in ("hide_render", "hide_viewport"):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"


def unit_bone_mesh(bpy):
    """Unit-radius cylinder from y=0 to y=1 (Stretch To works along local
    Y); each bone object scales X/Z to its own radius."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=1.0, depth=1.0)
    ob = bpy.context.active_object
    ob.rotation_euler = (math.pi / 2, 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    for v in ob.data.vertices:
        v.co.y += 0.5          # base at origin
    _shade_smooth(ob)
    me = ob.data
    me.materials.append(None)      # one slot; each object links its own
    bpy.data.objects.remove(ob)
    return me


def unit_ball_mesh(bpy):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12)
    ob = bpy.context.active_object
    _shade_smooth(ob)
    me = ob.data
    me.materials.append(None)      # one slot; each object links its own
    bpy.data.objects.remove(ob)
    return me


def figure_scale(T, name):
    """Size factor of a character relative to a default PAM figure, so
    small characters (scaled figures, dogs) get proportionally thinner
    limbs."""
    ys = [p[1] for p in T["initial"][name].values()]
    return float(np.clip((max(ys) - min(ys)) / REF_HEIGHT, 0.3, 1.5))


def edge_radius(a, b, sf, look):
    if look == "flat":
        return BONE_R
    if {a, b} in ({"neck", "lshoulder"}, {"neck", "rshoulder"}):
        r = SHOULDER_R
    elif {a, b} & {"head"}:
        r = NECK_R
    elif {a, b} & TORSO_JOINTS:
        r = TORSO_R
    else:
        r = LIMB_R
    return r * sf


def ground_level(T):
    """Lowest ankle/paw height anywhere in the trace (the stage floor)."""
    lo = None
    for name, info in T["cast"].items():
        feet = [j for j in info["joints"] if "ankle" in j or "paw" in j]
        if not feet:
            continue
        cands = [T["initial"].get(name) or {}]
        cands += [p["to"] for p in T["tracks"].get(name, [])]
        for c in cands:
            for j in feet:
                if j in c:
                    lo = c[j][1] if lo is None else min(lo, c[j][1])
    return lo


def floor_schedule(T):
    """[(t, ground_y)]: the floor height for each stretch of the film,
    taken as the lowest foot among the characters on stage whenever the
    cast on stage changes.  Scenes stand characters at different
    heights, so one floor for the whole film would leave some floating."""
    feet = {n: [j for j in info["joints"] if "ankle" in j or "paw" in j]
            for n, info in T["cast"].items()}
    tracks = {n: sorted(T["tracks"].get(n, []), key=lambda p: p["t1"])
              for n in T["cast"]}

    def pos_at(n, t):
        cur = T["initial"].get(n) or {}
        for p in tracks[n]:
            if p["t1"] <= t + 1e-6:
                cur = p["to"]
            else:
                break
        return cur

    events = sorted({row[0] for rows in T["visibility"].values()
                     for row in rows})
    state = {n: False for n in T["cast"]}
    vis_rows = {n: sorted(T["visibility"].get(n, [])) for n in T["cast"]}
    out = []
    for t in events:
        for n, rows in vis_rows.items():
            for tt, on, _ in rows:
                if tt <= t + 1e-6:
                    state[n] = bool(on)
        ys = []
        for n, on in state.items():
            if on and feet[n]:
                c = pos_at(n, t + 0.5)        # just after a fade-in starts
                ys += [c[j][1] for j in feet[n] if j in c]
        if ys:
            g = min(ys)
            if not out or abs(out[-1][1] - g) > 0.05:
                out.append((t, g))
    return out


def setup_look(bpy, sc, T, opt, bg_rgb):
    """Render engine, lights and stage for the chosen --look."""
    if opt.look == "flat":
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = "FLAT"
        sh.color_type = "MATERIAL"
        sh.background_type = "WORLD"
        return
    if opt.look == "studio":
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.background_type = "WORLD"
        sh.show_shadows = True
        sh.show_cavity = True
        sh.show_specular_highlight = True
        sh.shadow_intensity = 0.6
        sc.display.light_direction = (0.4, -0.6, 0.7)
    else:                                              # "eevee"
        engines = [e.identifier for e in
                   sc.render.bl_rna.properties["engine"].enum_items]
        sc.render.engine = next(e for e in ENGINE_EEVEE if e in engines)
        ee = sc.eevee
        for attr, val in (("taa_render_samples", 32), ("use_soft_shadows", True),
                          ("use_gtao", True), ("gtao_distance", 1.0),
                          ("use_shadows", True)):
            if hasattr(ee, attr):
                try:
                    setattr(ee, attr, val)
                except Exception:
                    pass
        # key light: sun from the front-left, casting shadows back onto
        # the floor and the back wall
        sun = bpy.data.lights.new("Key", "SUN")
        sun.energy = 3.5
        if hasattr(sun, "angle"):
            sun.angle = math.radians(4)
        so = bpy.data.objects.new("Key", sun)
        so.rotation_euler = (math.radians(42), 0, math.radians(-28))
        sc.collection.objects.link(so)
        # soft fill near the camera (no shadows)
        fill = bpy.data.lights.new("Fill", "AREA")
        fill.energy = 900
        fill.size = 12
        if hasattr(fill, "use_shadow"):
            fill.use_shadow = False
        fo = bpy.data.objects.new("Fill", fill)
        fo.location = (6, -14, 4)
        fo.rotation_euler = (math.radians(75), 0, math.radians(25))
        sc.collection.objects.link(fo)
        try:
            sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
        except Exception:
            pass
    # stage: floor at the on-stage characters' feet and a back wall
    sched = floor_schedule(T)
    if not sched:
        g = ground_level(T)
        if g is None:
            return
        sched = [(0.0, g)]
    stage = material(bpy, "Stage", tuple(min(1.0, c * 2.2 + 0.01) for c in bg_rgb)
                     + (1.0,), roughness=0.8)
    floor_z = sched[0][1] - LIMB_R * 0.6
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, floor_z))
    fl = bpy.context.active_object
    fl.name = "Floor"
    fl.data.materials.append(stage)
    if len(sched) > 1:
        for k, (t, g) in enumerate(sched):
            fl.location.z = g - LIMB_R * 0.6
            fl.keyframe_insert("location", index=2,
                               frame=1.0 if k == 0 else 1 + t * opt.fps)
        for fc in _id_fcurves(fl):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    # tall enough to reach below the floor at every height it takes
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 4.0, floor_z),
                                     rotation=(math.pi / 2, 0, 0))
    wl = bpy.context.active_object
    wl.name = "BackWall"
    wl.data.materials.append(stage)


def _rounded_rect(w, h, r, n=6):
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cz, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def _flat_mesh(bpy, name, pts2d, y):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, z) for x, z in pts2d], [], [list(range(len(pts2d)))])
    me.update()
    return me


def _font(bpy):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return bpy.data.fonts.load(p, check_existing=True)
            except Exception:
                pass
    return None


def _font_metrics(bpy, font):
    """Character advance and line height of *font* at size 1, measured
    once from a probe text object."""
    cu = bpy.data.curves.new("_probe", "FONT")
    if font is not None:
        cu.font = font
    cu.size = 1.0
    ob = bpy.data.objects.new("_probe", cu)
    bpy.context.scene.collection.objects.link(ob)
    cu.body = "M" * 20
    bpy.context.view_layer.update()
    adv = ob.dimensions.x / 20.0
    cu.body = "M\nM\nM\nM"
    bpy.context.view_layer.update()
    line_h = ob.dimensions.y / 4.0
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return max(adv, 1e-3), max(line_h, 1e-3)


def has_chest(joints, look):
    return look != "flat" and all(j in joints for j in CHEST_CORNERS)


def is_torso_edge(a, b):
    """Edges that the chest slab replaces: the struts inside the torso
    (shoulders/hips to the torso joints) and the shoulder and hip bars."""
    inner = {"torso", "torso_left", "torso_right"}
    ends = {a, b}
    if ends & inner:
        return not ends & {"neck", "head"}
    return ends in ({"lshoulder", "rshoulder"}, {"lhip", "rhip"})


def is_female(name, info, opt):
    """--female/--male override the screenplay; otherwise the cast's
    "gender", and a "narrow" build counts as female when none is given."""
    if name in opt.female:
        return True
    if name in opt.male:
        return False
    g = (info.get("gender") or "").lower()
    if g:
        return g == "female"
    return (info.get("build") or "") == "narrow"


def chest_corner_values(V, joints, female, sf):
    """Chest corner positions for every key (columns x, y for the four
    corners in CHEST_CORNERS order), derived from the shoulders and hips.
    Male: the joints' own spread plus padding (wide top, narrow bottom).
    Female: a narrower top and a wider bottom.  Both keep a minimum width
    so a side view still shows a body."""
    ji = {j: i for i, j in enumerate(joints)}
    P = lambda j: V[:, 2 * ji[j]:2 * ji[j] + 2]
    ls, rs, rh, lh = (P(j) for j in CHEST_CORNERS)
    pad = CHEST_PAD * sf / 2

    def frame(a, b):
        mid = (a + b) / 2
        half = (b - a) / 2
        n = np.linalg.norm(half, axis=1)
        d = np.where(n[:, None] > 1e-4, half / np.maximum(n, 1e-9)[:, None],
                     np.array([1.0, 0.0]))
        return mid, d, n

    ms, ds, ns = frame(ls, rs)
    mh, dh, nh = frame(lh, rh)
    if female:
        top = FEMALE_TOP * ns + pad
        bot = np.maximum(nh + pad, FEMALE_FLARE * top)
    else:
        top = ns + pad
        bot = nh + pad
    out = [ms - ds * top[:, None], ms + ds * top[:, None],
           mh + dh * bot[:, None], mh - dh * bot[:, None]]
    return np.concatenate(out, axis=1)


def bust_values(CV):
    """Per-key centers of the two bust shapes: points on the upper
    chest, a bilinear blend of the four chest corners."""
    ls, rs, rh, lh = (CV[:, 2 * i:2 * i + 2] for i in range(4))
    out = []
    for u in (BUST_U, 1 - BUST_U):
        v = BUST_V
        out.append((1 - u) * (1 - v) * ls + u * (1 - v) * rs
                   + u * v * rh + (1 - u) * v * lh)
    return np.concatenate(out, axis=1)


def build_chest(bpy, col, name, corners, mat, sf, female):
    """A solid chest: a subdivided box whose surface is a bilinear blend
    of four corner empties (hook modifiers with bilinear vertex weights),
    beveled for a rounded look.  (Female busts are separate objects; see
    bust_values.)"""
    import bmesh
    d = CHEST_DEPTH * sf / 2
    nu = nv = CHEST_GRID
    bm = bmesh.new()
    front, back = {}, {}
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            front[i, j] = bm.verts.new((0.0, -d, 0.0))
            back[i, j] = bm.verts.new((0.0, d, 0.0))
    for j in range(nv):
        for i in range(nu):
            bm.faces.new([front[i, j], front[i + 1, j], front[i + 1, j + 1],
                          front[i, j + 1]])
            bm.faces.new([back[i, j + 1], back[i + 1, j + 1], back[i + 1, j],
                          back[i, j]])
    ring = ([(i, 0) for i in range(nu)] + [(nu, j) for j in range(nv)]
            + [(i, nv) for i in range(nu, 0, -1)] + [(0, j) for j in range(nv, 0, -1)])
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        bm.faces.new([front[a], front[b], back[b], back[a]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(f"{name}.chest")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"{name}.chest", me)
    col.objects.link(ob)
    ob.data.materials.append(mat)
    # bilinear corner weights: (u, v) = (0,0) ls, (1,0) rs, (1,1) rh, (0,1) lh
    groups = [ob.vertex_groups.new(name=c) for c in CHEST_CORNERS]
    for vtx in me.vertices:
        idx = vtx.index // 2
        i, j = idx % (nu + 1), idx // (nu + 1)
        u, v = i / nu, j / nv
        for g, w in zip(groups, ((1 - u) * (1 - v), u * (1 - v), u * v,
                                 (1 - u) * v)):
            if w > 0:
                g.add([vtx.index], w, "REPLACE")
    for g, corner in zip(groups, CHEST_CORNERS):
        h = ob.modifiers.new(f"hook {corner}", "HOOK")
        h.object = corners[corner]
        h.vertex_group = g.name
    bev = ob.modifiers.new("round", "BEVEL")
    bev.width = 0.06 * sf
    bev.segments = 3
    if hasattr(bev, "limit_method"):
        bev.limit_method = "ANGLE"
    for poly in me.polygons:
        poly.use_smooth = True
    return ob


def narrow_hips(keys, joints, f):
    """Pull the two hip joints toward their midpoint by factor *f* in
    every key (male figures: narrower hips under wide shoulders).  The
    chest's bottom corners follow; knees and feet are not moved."""
    if "lhip" not in joints or "rhip" not in joints or not keys.v:
        return
    li, ri = joints.index("lhip"), joints.index("rhip")
    keys.v = [np.array(v, float) for v in keys.v]    # rows may share memory
    for v in keys.v:
        L = v[2 * li:2 * li + 2].copy()
        R = v[2 * ri:2 * ri + 2].copy()
        mid = (L + R) / 2
        v[2 * li:2 * li + 2] = mid + (L - mid) * f
        v[2 * ri:2 * ri + 2] = mid + (R - mid) * f


def _toe_angle(piece, prev):
    """Shoe heading (rotation about z) for a motion piece: 0 points the
    toes at the camera (front view); side views point them toward the
    figure's facing."""
    view = piece.get("view")
    if view == "front":
        return 0.0
    if view == "side":
        f = (piece.get("facing") or "right").lower()
        return -math.pi / 2 if f in ("left", "lside") else math.pi / 2
    return prev


def shoe_keys(T, name, fps):
    """Shoe heading keys: held between moves, turning during each move
    that changes the view (a turn)."""
    keys = KeyList(fps)
    tr = sorted(T["tracks"].get(name, []), key=lambda p: (p["t0"], p["t1"]))
    ang = None
    for p in tr:
        a = _toe_angle(p, ang)
        if a is None:
            continue
        if ang is None:
            keys.add(0.0, [a])
        elif abs(a - ang) > 1e-6:
            keys.add(p["t0"], [ang])
            keys.add(p["t1"], [a])
        ang = a
    if not keys.f:
        keys.add(0.0, [0.0])
    return keys


def build_shoes(bpy, col, name, empties, sf, shoe_mat, ball_me, T, fps):
    """An ellipsoid shoe under each ankle, its bottom on the floor when
    the foot is planted, turned to match the figure's view."""
    out = []
    keys = shoe_keys(T, name, fps)
    L, W, H = SHOE_L * sf, SHOE_W * sf, SHOE_H * sf
    for side in ("l", "r"):
        ank = empties.get(f"{side}ankle")
        if ank is None:
            continue
        piv = bpy.data.objects.new(f"{name}.{side}shoe.pivot", None)
        piv.empty_display_size = 0.05
        col.objects.link(piv)
        piv.parent = ank
        apply_keys(bpy, piv, "rotation_euler", [(2, 0, lambda v: v)], keys)
        shoe = bpy.data.objects.new(f"{name}.{side}shoe", ball_me)
        col.objects.link(shoe)
        shoe.material_slots[0].link = "OBJECT"
        shoe.material_slots[0].material = shoe_mat
        shoe.parent = piv
        # the floor sits LIMB_R * 0.6 below a planted ankle (setup_look)
        shoe.location = (0.0, -SHOE_FWD * sf, -LIMB_R * 0.6 + H / 2)
        shoe.scale = (W / 2, L / 2, H / 2)
        out.append(shoe)
    return out


BUBBLE_Y = -1.5            # bubble panels' depth (in front of the cast)
BUBBLE_MARGIN = 0.12       # keep bubbles this far inside the camera frame


def _move_eval(c0, moves, rates, t, key=None):
    """Value at time t of something that starts at c0 and changes by
    camera-style moves ({"t0", "t1", "rate", "from", "to"})."""
    get = key or (lambda v: np.asarray(v, float))
    cur = get(c0)
    for m in moves:
        if m["t0"] > t + 1e-9:
            break
        a0, a1 = get(m["from"]), get(m["to"])
        if m["t1"] <= t or m["t1"] <= m["t0"]:
            cur = a1
            continue
        r = rates.get(m["rate"]) or rates["linear"]
        x = float(r(np.array([(t - m["t0"]) / (m["t1"] - m["t0"])]))[0])
        if abs(r.end - 1) > 1e-6 and abs(r.end) > 1e-6:
            x /= r.end
        cur = a0 + x * (a1 - a0)
    return cur


def camera_at(T, rates, t):
    """(center x, center y, width) of the Manim camera frame at time t."""
    c0 = T.get("camera_initial") or {"center": [0, 0],
                                     "width": T["frame"]["width"]}
    return _move_eval(c0, T.get("camera", []), rates, t,
                      key=lambda c: np.array([c["center"][0], c["center"][1],
                                              c["width"]], float))


def bubble_track(b, T, rates, opt, tilt):
    """Keys (t, [x, z]) for a bubble: its Manim position, nudged so the
    whole bubble stays inside the camera frame while it is shown.  PAM
    places bubbles by the speaker in world space, so in close-ups part of
    a bubble can fall outside the frame (in the Manim video too)."""
    rows = b.get("visibility") or []
    spans = []
    for k, (t, on) in enumerate(rows):
        if on:
            spans.append((t, rows[k + 1][0] if k + 1 < len(rows) else T["duration"]))
    ct, st = math.cos(tilt), math.sin(tilt)
    aspect = opt.res[1] / opt.res[0]
    border = 0.035
    hw = b["w"] / 2 + border
    top = b["h"] / 2 + border
    tail = [p[1] for p in (b.get("tail") or [])]
    bot = max(b["h"] / 2 + border, -min(tail) if tail else 0.0)
    out, nudged = [], False
    for ta, tb in spans:
        ts = np.concatenate([[ta], _inner_times(ta, tb, opt.fps), [tb]])
        for t in ts:
            x, z = _move_eval(b["initial"], b.get("moves", []), rates, t)
            cx, cy, W = camera_at(T, rates, t)
            H = W * aspect
            m = BUBBLE_MARGIN * W / 14.2
            lo, hi = cx - W / 2 + m + hw, cx + W / 2 - m - hw
            nx = cx if lo > hi else min(max(x, lo), hi)
            # screen height of a point at depth y: y*sin(tilt) + (z-cy)*cos
            zhi = cy + (H / 2 - m - BUBBLE_Y * st) / ct - top
            zlo = cy + (-H / 2 + m - BUBBLE_Y * st) / ct + bot
            nz = min(max(z, zlo), zhi) if zlo <= zhi else zhi
            nudged |= abs(nx - x) > 1e-4 or abs(nz - z) > 1e-4
            out.append((float(t), [nx, nz]))
    return out, nudged


def build_bubbles(bpy, sc, T, rates, opt, native, tilt):
    """Speech bubbles as camera-facing panels: rounded box with a border,
    tail, and real text, shown and moved exactly as in the trace."""
    bubbles = T.get("bubbles") or []
    if not bubbles:
        return 0
    col = bpy.data.collections.new("bubbles")
    sc.collection.children.link(col)
    font = _font(bpy)
    mats = {}
    adv, line_h = _font_metrics(bpy, font)
    nbubble_nudged = [0]

    def mat(hx):
        if hx not in mats:
            mats[hx] = material(bpy, "bubble " + hx, hex_rgba(hx), emission=True)
        return mats[hx]

    for b in bubbles:
        if not b.get("visibility"):
            continue
        root = bpy.data.objects.new(f"bubble.{b['id']}", None)
        root.empty_display_size = 0.2
        col.objects.link(root)
        root.rotation_euler = (-tilt, 0, 0)       # face the tilted camera
        parts = []
        w, h = b["w"], b["h"]
        os_style = b.get("style") in ("os", "phone", "aside")
        border = 0.035
        # border (stroke color) behind, fill in front
        me = _flat_mesh(bpy, "bubble border", _rounded_rect(w + 2 * border,
                        h + 2 * border, 0.15 + border), 0.012)
        ob = bpy.data.objects.new(f"bubble.{b['id']}.border", me)
        ob.data.materials.append(mat(b["stroke"]))
        parts.append(ob)
        if not (os_style and b.get("fill_opacity", 1) < 0.05):
            me = _flat_mesh(bpy, "bubble box", _rounded_rect(w, h, 0.15), 0.0)
            ob = bpy.data.objects.new(f"bubble.{b['id']}.box", me)
            ob.data.materials.append(mat(b["fill"]))
            parts.append(ob)
        if len(b.get("tail") or []) == 3:
            tail = [(x, z) for x, z in b["tail"]]
            me = _flat_mesh(bpy, "bubble tail", tail, 0.0)
            ob = bpy.data.objects.new(f"bubble.{b['id']}.tail", me)
            ob.data.materials.append(mat(b["fill"] if not os_style else b["stroke"]))
            parts.append(ob)
        # text
        cu = bpy.data.curves.new(f"bubble.{b['id']}.text", "FONT")
        cu.body = b["text"]
        if font is not None:
            cu.font = font
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.size = 1.0
        tx = bpy.data.objects.new(f"bubble.{b['id']}.text", cu)
        tx.rotation_euler = (math.pi / 2, 0, 0)
        tx.location = (0, -0.01, 0)
        cu.materials.append(mat(b["text_color"]))
        parts.append(tx)
        for ob in parts:
            col.objects.link(ob)
            ob.parent = root
            if hasattr(ob, "visible_shadow"):
                ob.visible_shadow = False
        # scale the text to Manim's measured text size (monospace font:
        # width = longest line x advance, height = lines x line height)
        lines = b["text"].split("\n") or [""]
        dw = max(len(ln) for ln in lines) * adv
        dh = len(lines) * line_h
        if dw > 1e-6 and dh > 1e-6:
            # match Manim's text width, but keep the lines inside the box
            cu.size = min(b["text_w"] / dw, 0.9 * b["h"] / dh)
        # position (front of the characters) and moves
        keys = KeyList(opt.fps)
        track, nudged = bubble_track(b, T, rates, opt, tilt)
        if nudged:
            # kept inside the camera frame: baked over its time on screen
            for t, v in track:
                keys.add(t, v)
            if track and track[0][0] > 0:
                keys.f.insert(0, 1.0)
                keys.v.insert(0, np.asarray(track[0][1], float))
                keys.spec.insert(0, ("CONSTANT", "AUTO"))
            nbubble_nudged[0] += 1
        else:
            keys.add(0.0, b["initial"])
            for mv in b.get("moves", []):
                if mv["t1"] <= mv["t0"]:
                    keys.add(mv["t0"], mv["from"]); keys.add(mv["t0"], mv["to"])
                    continue
                nat = native.get(mv["rate"])
                keys.add(mv["t0"], mv["from"],
                         (nat[0], nat[1]) if nat else ("LINEAR", "AUTO"))
                keys.add(mv["t1"], mv["to"])
        root.location = (b["initial"][0], BUBBLE_Y, b["initial"][1])
        if len(keys.f) > 1:
            apply_keys(bpy, root, "location",
                       [(0, 0, lambda v: v), (2, 1, lambda v: v)], keys)
        # visibility, keyed only at changes
        seq = [(0.0, False)] + [(t, bool(on)) for t, on in b["visibility"]]
        key_visibility(parts, seq, opt.fps)
    print(f"bubbles kept inside the camera frame: {nbubble_nudged[0]} "
          f"of {len(bubbles)}")
    return len(bubbles)


# ═════════════════════════════════════════════════════════════════════════
#  Props and scene objects (trace version 3)
# ═════════════════════════════════════════════════════════════════════════
#
# Each prop gets a root empty whose keyed location follows the prop's free
# path (Manim x -> Blender x, Manim y -> Blender z, plus a depth y chosen
# by prop kind).  While a figure holds the prop, Copy Location constraints
# (with "offset", Y left alone) add the holding joint(s) to the root's own
# location, which is then keyed to the small hold offset; their influence
# switches on at the attach and ramps off during the release move (the
# place_on slide), so the prop travels from the Blender hand to its rest.

WALL_Y = 4.0                 # back wall plane (see setup_look)
FURN_Y, FURN_D = 0.75, 0.90  # desks / tables: center depth and depth size
CHAIR_Y, CHAIR_D = 0.35, 0.50
LOOSE_Y = 0.30               # free-standing small props, just behind the cast
HOLD_Y = -0.20               # held props, just in front of the hands
GOV_Y = 0.50
REST_TILT = math.radians(25)  # a phone left on a table leans back this far
                              # from flat, so the camera still sees its face
SPIN_DEFAULT = 0.35          # rad/s, GovernorGraph's spin rate
AMBER_SPIN = 0.3             # low-power spin, as a fraction of normal
RELEASE_WINDOW = (-0.05, 0.35)   # a move starting this soon after a
                                 # release is the release's own motion

DESK_TYPES = {"desk", "table", "console", "computer", "workstation",
              "terminal"}
FLOOR_TYPES = DESK_TYPES | {"chair", "door", "pocket_door", "elevator",
                            "avatar_pod", "pod", "potted_plant", "plant",
                            "building"}
BACK_TYPES = {"door": WALL_Y - 0.06, "pocket_door": WALL_Y - 0.06,
              "elevator": WALL_Y - 0.10, "backdrop": WALL_Y - 0.10,
              "tv_monitor": WALL_Y - 0.10, "monitor": WALL_Y - 0.10,
              "building": WALL_Y - 0.60, "sun": WALL_Y - 0.15,
              "moon": WALL_Y - 0.15}


def prop_type(rec):
    spec = rec.get("spec") or {}
    t = spec.get("type") if spec.get("action") != "spawn_prop" or \
        spec.get("type") else None
    return str(t or rec.get("type") or "").lower()


def prop_kind(rec):
    """Which builder makes this prop: "governor", "dodecahedron", "desk",
    "table", "door", "chair", "phone" or the generic "cutout"."""
    t = prop_type(rec)
    if rec.get("governor"):
        return "governor"
    if t == "dodecahedron":
        return "dodecahedron"
    if t == "table":
        return "table"
    if t in DESK_TYPES or rec.get("type") == "desk":
        return "desk"
    if t == "door":
        return "door"
    if t == "chair":
        return "chair"
    if rec.get("type") == "phone" and \
            (rec.get("meta") or {}).get("phone_style", "cellphone") == "cellphone":
        return "phone"
    return "cutout"


def _visible_from(rec):
    for t, on, _ in rec.get("visibility", []):
        if on:
            return t
    return None


def _floor_at(sched, t):
    """Floor z (as built by setup_look) in effect at time t."""
    if not sched:
        return None
    g = sched[0][1]
    for ts, gy in sched:
        if ts <= t + 1e-6:
            g = gy
        else:
            break
    return g - LIMB_R * 0.6


class PropPlan:
    """Layout decisions for one prop record (pure Python; no bpy)."""

    def __init__(self, rec, sched):
        self.rec = rec
        self.kind = prop_kind(rec)
        self.type = prop_type(rec)
        self.meta = rec.get("meta") or {}
        self.spec = rec.get("spec") or {}
        box = (rec.get("geometry") or {}).get("box") or rec["initial"]
        self.box = box                       # geometry reference box
        self.cx, self.cy, self.w, self.h = box
        self.t_vis = _visible_from(rec)
        k = self.kind
        # depth (Blender y) of the prop's center when free
        if k in ("desk", "table"):
            self.depth, self.dsize = FURN_Y, FURN_D
        elif k == "chair":
            self.depth, self.dsize = CHAIR_Y, CHAIR_D
        elif k in ("governor", "dodecahedron"):
            self.depth, self.dsize = GOV_Y, self.w
        elif self.type in BACK_TYPES:
            self.depth, self.dsize = BACK_TYPES[self.type], 0.1
        else:
            self.depth, self.dsize = LOOSE_Y, 0.06
        # thickness when lying flat on a surface
        self.thick = 0.035 * max(self.w / 0.22, 0.5) if k == "phone" else 0.04
        # floor snap: floor-standing props sit on the stage floor
        self.dz = 0.0
        bottom = self.meta.get("y") if k in ("desk", "table", "door",
                                             "chair") else None
        if bottom is None:
            bottom = rec["initial"][1] - rec["initial"][3] / 2
        self.bottom = bottom
        fz = _floor_at(sched, self.t_vis if self.t_vis is not None else 0.0)
        if fz is not None:
            gap = fz - bottom
            if self.type in FLOOR_TYPES or k in ("desk", "table", "door",
                                                 "chair"):
                if abs(gap) < 1.5:
                    self.dz = gap
            elif 0.0 < gap < 1.0 and not rec.get("holds"):
                self.dz = gap                # never leave a prop buried
        # top surface (for props placed on this one), in Manim units
        st = self.meta.get("surface_y")
        self.top_manim = st if (st is not None and k in ("desk", "table",
                                                         "chair")) \
            else rec["initial"][1] + rec["initial"][3] / 2

    @property
    def top_z(self):
        return self.top_manim + self.dz

    def rest_y(self):
        """Depth where a prop placed on this one rests: near its front."""
        return self.depth - self.dsize / 2 + min(0.3, self.dsize / 2)


def _parent_changes(rec):
    """[(t_effective, parent)]: a parent set at the end of place_on applies
    from the end of the move that carried the prop there."""
    out = []
    moves = rec.get("moves", [])
    prev = -1.0
    for t, parent in rec.get("parents", []):
        eff = t
        for m in moves:
            if prev < m["t1"] <= t + 1e-6 and m["t1"] > m["t0"]:
                eff = m["t1"]
        out.append((eff, parent))
        prev = eff
    return out


def _find_plan(plans, name, t):
    best = None
    for p in plans:
        if p.rec["name"] == name and (p.t_vis is None or p.t_vis <= t + 1e-6):
            best = p
    return best


def prop_placement(plan, plans, pchanges, t):
    """(depth y, z of the box center for Manim center y=None, lying) at
    time t.  Returns (y, z_override, dz, lying)."""
    parent = None
    for te, pn in pchanges:
        if te <= t + 1e-6:
            parent = pn
    if parent:
        P = _find_plan(plans, parent, t)
        if P is not None and P is not plan:
            lying = plan.kind == "phone"
            half = (plan.h / 2 * math.sin(REST_TILT)
                    + plan.thick / 2 * math.cos(REST_TILT)) if lying \
                else plan.h / 2
            return P.rest_y(), P.top_z + half, P.dz, lying
    return plan.depth, None, plan.dz, False


def prop_keys(plan, plans, T, rates, opt, native, joints_of):
    """Keys for one prop's root: columns x, y, z, rot_x, scale, then one
    influence column per (char, joint) hold constraint.  Returns
    (KeyList, constraint list [(char, joint)])."""
    rec = plan.rec
    pch = _parent_changes(rec)
    cons = []
    holds = []
    for h in rec.get("holds", []):
        js = [j for j in h["joints"] if j in joints_of.get(h["char"], ())]
        if not js or h.get("t1") is None or h["t1"] <= h["t0"]:
            continue
        for j in js:
            if (h["char"], j) not in cons:
                cons.append((h["char"], j))
        holds.append((h, js))
    nc = len(cons)
    w0 = plan.w if plan.w > 1e-6 else 1.0

    def free_vec(box, t):
        y, zo, dz, lying = prop_placement(plan, plans, pch, t)
        z = zo if zo is not None else box[1] + dz
        s = box[2] / w0 if plan.kind in ("governor", "dodecahedron",
                                         "cutout") else 1.0
        rot = -(math.pi / 2 - REST_TILT) if lying else 0.0
        return [box[0], y, z, rot, s] + [0.0] * nc

    # free path: (t, vec, spec)
    free = []
    cur = rec["initial"]
    free.append((0.0, free_vec(cur, 0.0), ("LINEAR", "AUTO")))
    for m in rec.get("moves", []):
        nat = native.get(m["rate"]) if m["t1"] > m["t0"] else None
        free.append((m["t0"], free_vec(m["from"], m["t0"]),
                     (nat[0], nat[1]) if nat else ("LINEAR", "AUTO")))
        if nat is None and m["t1"] > m["t0"] and m["rate"] in rates:
            r = rates[m["rate"]]
            ts = _inner_times(m["t0"], m["t1"], opt.fps)
            a, b = np.array(m["from"], float), np.array(m["to"], float)
            for t in ts:
                al = r((t - m["t0"]) / (m["t1"] - m["t0"]))
                free.append((t, free_vec(list(a + al * (b - a)), t),
                             ("LINEAR", "AUTO")))
        free.append((m["t1"], free_vec(m["to"], m["t1"]), ("LINEAR", "AUTO")))
        cur = m["to"]
    # parent changes without a move (e.g. a prop declared on a desk)
    for te, _ in pch:
        box = rec["initial"]
        for m in rec.get("moves", []):
            if m["t1"] <= te + 1e-6:
                box = m["to"]
        free.append((te, free_vec(box, te + 1e-6), ("LINEAR", "AUTO")))
    free.sort(key=lambda k: k[0])

    def free_at(t):
        v = free[0][1]
        for tk, vk, _ in free:
            if tk <= t + 1e-6:
                v = vk
            else:
                break
        return list(v)

    # hold spans
    spans = []
    for h, js in holds:
        vec_h = None
        off = h.get("offset") or [0.0, 0.0]
        hy = HOLD_Y if h.get("start") != "follows" else 0.0
        t_rel = h["t1"]
        ramp = None
        if h.get("end") not in ("exit", "handoff", "follows"):
            for m in rec.get("moves", []):
                if RELEASE_WINDOW[0] <= m["t0"] - t_rel <= RELEASE_WINDOW[1] \
                        and m["t1"] > m["t0"]:
                    ramp = m
                    break
        infl = [0.0] * nc
        for j in js:
            infl[cons.index((h["char"], j))] = 1.0 / len(js)
        vec_h = [off[0], hy, off[1], 0.0, 1.0] + infl
        spans.append((h, vec_h, ramp))

    def in_span(t):
        for h, _, ramp in spans:
            end = ramp["t1"] if ramp else h["t1"]
            if h["t0"] - 1e-6 <= t < end - 1e-6:
                return True
        return False

    events = [(tk, 0, vk, sp) for tk, vk, sp in free if not in_span(tk)]
    for h, vec_h, ramp in spans:
        events.append((h["t0"], 1, free_at(h["t0"] - 1e-4), ("CONSTANT", "AUTO")))
        events.append((h["t0"], 2, vec_h, ("LINEAR", "AUTO")))
        if ramp is not None:
            nat = native.get(ramp["rate"])
            spec = (nat[0], nat[1]) if nat else ("SINE", "EASE_IN_OUT")
            events.append((ramp["t0"], 3, vec_h, spec))
            events.append((ramp["t1"], 4, free_at(ramp["t1"]), ("LINEAR", "AUTO")))
        else:
            events.append((h["t1"], 3, vec_h, ("CONSTANT", "AUTO")))
            events.append((h["t1"], 4, free_at(h["t1"]), ("LINEAR", "AUTO")))
    events.sort(key=lambda e: (e[0], e[1]))
    keys = KeyList(opt.fps)
    for t, _, v, sp in events:
        keys.add(max(t, 0.0), v, sp)
    return keys, cons


def _box_mesh(bpy, name, sx, sy, sz, loc=(0, 0, 0), bevel=0.0):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * sx + loc[0]
        v.co.y = v.co.y * sy + loc[1]
        v.co.z = v.co.z * sz + loc[2]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _cyl_mesh(bpy, name, r, z0, z1, x, y, verts=12):
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r,
                          radius2=r, depth=z1 - z0)
    for v in bm.verts:
        v.co.x += x
        v.co.y += y
        v.co.z += (z0 + z1) / 2
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _dodeca_mesh(bpy, name, radius):
    """A regular dodecahedron (pentagon faces) with the given
    circumradius."""
    import bmesh
    phi = (1 + 5 ** 0.5) / 2
    pts = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    for a in (-1, 1):
        for b in (-1, 1):
            pts += [(0, a / phi, b * phi), (a / phi, b * phi, 0),
                    (b * phi, 0, a / phi)]
    k = radius / 3 ** 0.5
    bm = bmesh.new()
    vs = [bm.verts.new((x * k, y * k, z * k)) for x, y, z in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0),
                             verts=bm.verts, edges=bm.edges)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def _mix(h1, h2, a):
    c1, c2 = hex_rgba(h1), hex_rgba(h2)
    return tuple(c1[i] * (1 - a) + c2[i] * a for i in range(3)) + (1.0,)


class PropBuilder:
    def __init__(self, bpy, sc, T, rates, opt, native):
        self.bpy, self.sc, self.T = bpy, sc, T
        self.rates, self.opt, self.native = rates, opt, native
        self.mats = {}
        self.col = bpy.data.collections.new("props")
        sc.collection.children.link(self.col)
        self.font = None

    def mat(self, key, color, roughness=0.5, metallic=0.0, emission=None,
            strength=0.0):
        if key in self.mats:
            return self.mats[key]
        m = material(self.bpy, "prop " + key, color, roughness=roughness)
        nt = getattr(m, "node_tree", None)
        try:
            b = nt.nodes["Principled BSDF"]
            b.inputs["Metallic"].default_value = metallic
            if emission is not None:
                ec = _socket(b, "Emission Color", "Emission")
                es = _socket(b, "Emission Strength")
                if ec is not None:
                    ec.default_value = emission
                if es is not None:
                    es.default_value = strength
        except Exception as exc:
            print("prop material:", exc)
        self.mats[key] = m
        return m

    def obj(self, name, data, parent, mat=None, loc=(0, 0, 0)):
        ob = self.bpy.data.objects.new(name, data)
        self.col.objects.link(ob)
        ob.parent = parent
        ob.location = loc
        if mat is not None and data is not None:
            data.materials.append(mat)
        return ob

    # ── models (local coordinates: origin = Manim box center) ──────────
    def build_desk(self, plan, root, tag):
        rec, m = plan.rec, plan.meta
        fill = rec["colors"].get("fill") or "#1a2a3a"
        stroke = rec["colors"].get("stroke") or "#5588aa"
        if plan.spec.get("monitor"):
            fill = "#1a2a3a"                 # the box color is the screen's
            for p in (rec.get("geometry") or {}).get("parts", []):
                if p["fill"].lower() != "#1af0c4" and p["fill_opacity"] > 0.5:
                    fill = p["fill"]
                    break
        top_m = self.mat("desk top " + fill + stroke, _mix(fill, stroke, 0.45),
                         roughness=0.45)
        leg_m = self.mat("desk leg " + stroke, hex_rgba(stroke), roughness=0.4,
                         metallic=0.3)
        W = float(plan.spec.get("length") or plan.spec.get("width") or plan.w)
        x0 = (m.get("x", plan.cx)) - plan.cx
        top = m.get("surface_y", plan.cy + plan.h / 2) - plan.cy
        bot = m.get("y", plan.cy - plan.h / 2) - plan.cy
        D = plan.dsize
        out = []
        out.append(self.obj(tag + ".top", _box_mesh(self.bpy, tag + ".top",
                   W, D, 0.08, (x0, 0, top - 0.04)), root, top_m))
        for sx in (-1, 1):
            for sy in (-1, 1):
                out.append(self.obj(tag + ".leg", _cyl_mesh(
                    self.bpy, tag + ".leg", 0.035, bot, top - 0.08,
                    x0 + sx * (W / 2 - 0.1), sy * (D / 2 - 0.1)), root, leg_m))
        if plan.kind == "desk":              # modesty panel at the back
            out.append(self.obj(tag + ".panel", _box_mesh(
                self.bpy, tag + ".panel", W - 0.2, 0.03, (top - bot) * 0.45,
                (x0, D / 2 - 0.1, top - 0.08 - (top - bot) * 0.225)),
                root, top_m))
        if plan.spec.get("monitor"):
            mc = plan.spec.get("monitor_color") or "#1af0c4"
            scr_m = self.mat("screen " + mc, hex_rgba(mc), roughness=0.3,
                             emission=hex_rgba(mc), strength=1.2)
            mw, mh = 0.45, 0.35
            mz = top + 0.06 + mh / 2
            out.append(self.obj(tag + ".bezel", _box_mesh(
                self.bpy, tag + ".bezel", mw + 0.05, 0.05, mh + 0.05,
                (x0, -0.05, mz)), root, leg_m))
            out.append(self.obj(tag + ".screen", _box_mesh(
                self.bpy, tag + ".screen", mw, 0.01, mh, (x0, -0.08, mz)),
                root, scr_m))
            out.append(self.obj(tag + ".stand", _box_mesh(
                self.bpy, tag + ".stand", 0.08, 0.08, 0.08,
                (x0, -0.05, top + 0.03)), root, leg_m))
        return out

    def build_door(self, plan, root, tag):
        rec = plan.rec
        fill = rec["colors"].get("fill") or "#2a3a4a"
        stroke = rec["colors"].get("stroke") or "#667788"
        W, H = plan.w, plan.h
        panel_m = self.mat("door " + fill, _mix(fill, stroke, 0.25),
                           roughness=0.55)
        frame_m = self.mat("door frame " + stroke, hex_rgba(stroke),
                           roughness=0.4, metallic=0.2)
        knob_m = self.mat("door handle", hex_rgba("#cccccc"), roughness=0.25,
                          metallic=0.8)
        f = 0.08
        out = [self.obj(tag + ".panel", _box_mesh(self.bpy, tag + ".panel",
                        W - 0.02, 0.06, H - 0.01, (0, 0, -0.005)), root,
                        panel_m)]
        # recessed lower and upper panels for some relief
        for zc, hh in ((-H * 0.22, H * 0.38), (H * 0.24, H * 0.38)):
            out.append(self.obj(tag + ".inset", _box_mesh(
                self.bpy, tag + ".inset", W * 0.7, 0.02, hh, (0, -0.035, zc)),
                root, frame_m))
        for sx in (-1, 1):
            out.append(self.obj(tag + ".jamb", _box_mesh(
                self.bpy, tag + ".jamb", f, 0.16, H + f,
                (sx * (W / 2 + f / 2), 0, f / 2)), root, frame_m))
        out.append(self.obj(tag + ".header", _box_mesh(
            self.bpy, tag + ".header", W + 2 * f, 0.16, f,
            (0, 0, H / 2 + f / 2)), root, frame_m))
        hx = W / 2 - 0.15
        hz = -H / 2 + H * 0.45
        out.append(self.obj(tag + ".handle", _cyl_mesh(
            self.bpy, tag + ".handle", 0.025, hz - 0.12, hz + 0.12, hx, -0.07),
            root, knob_m))
        return out

    def build_chair(self, plan, root, tag):
        rec, m = plan.rec, plan.meta
        stroke = rec["colors"].get("stroke") or "#5588aa"
        fill = rec["colors"].get("fill") or "#1a2a3a"
        seat_m = self.mat("chair " + fill + stroke, _mix(fill, stroke, 0.45),
                          roughness=0.5)
        leg_m = self.mat("desk leg " + stroke, hex_rgba(stroke), roughness=0.4,
                         metallic=0.3)
        x0 = m.get("x", plan.cx) - plan.cx
        bot = m.get("y", plan.cy - plan.h / 2) - plan.cy
        seat = bot + 0.55
        D = plan.dsize
        out = [self.obj(tag + ".seat", _box_mesh(self.bpy, tag + ".seat",
                        0.7, D, 0.06, (x0, 0, seat)), root, seat_m),
               self.obj(tag + ".back", _box_mesh(self.bpy, tag + ".back",
                        0.06, D, 0.62, (x0 - 0.32, 0, seat + 0.34)), root,
                        seat_m)]
        for sx in (-1, 1):
            for sy in (-1, 1):
                out.append(self.obj(tag + ".leg", _cyl_mesh(
                    self.bpy, tag + ".leg", 0.025, bot, seat,
                    x0 + sx * 0.29, sy * (D / 2 - 0.05)), root, leg_m))
        return out

    def build_phone(self, plan, root, tag):
        rec = plan.rec
        body = (plan.spec.get("color") or rec["colors"].get("stroke")
                or "#223344")
        W, H, Tk = plan.w, plan.h, plan.thick
        body_m = self.mat("phone " + body, hex_rgba(body), roughness=0.3,
                          metallic=0.6)
        scr_m = self.mat("phone screen", hex_rgba("#0a1a2a"), roughness=0.15,
                         emission=hex_rgba("#1af0c4"), strength=0.25)
        out = [self.obj(tag + ".body", _box_mesh(self.bpy, tag + ".body",
                        W, Tk, H), root, body_m)]
        bev = out[0].modifiers.new("round", "BEVEL")
        bev.width = min(W, H) * 0.08
        bev.segments = 3
        out.append(self.obj(tag + ".screen", _box_mesh(
            self.bpy, tag + ".screen", W * 0.82, 0.004, H * 0.80,
            (0, -Tk / 2 - 0.002, H * 0.03)), root, scr_m))
        cam_m = self.mat("phone camera", hex_rgba("#333333"), roughness=0.2)
        out.append(self.obj(tag + ".cam", _cyl_mesh(
            self.bpy, tag + ".cam", W * 0.06, -0.006, 0.006, 0, 0), root,
            cam_m))
        out[-1].rotation_euler = (math.pi / 2, 0, 0)
        out[-1].location = (0, -Tk / 2 - 0.004, H / 2 - H * 0.07)
        return out

    def build_governor(self, plan, root, tag):
        """Gold dodecahedron with accent edges; returns (parts, spin
        empty, scale empty, face material)."""
        g = plan.rec.get("governor") or {}
        gold = g.get("gold") or plan.spec.get("color") or "#e8c547"
        accent = g.get("accent") or plan.spec.get("accent") or "#cc3333"
        r = float(g.get("radius") or 0.42) * 1.15
        pulse = self.bpy.data.objects.new(tag + ".pulse", None)
        self.col.objects.link(pulse)
        pulse.parent = root
        spin = self.bpy.data.objects.new(tag + ".spin", None)
        self.col.objects.link(spin)
        spin.parent = pulse
        face_m = material(self.bpy, f"{tag} faces", hex_rgba(gold),
                          roughness=0.25)
        nt = getattr(face_m, "node_tree", None)
        try:
            b = nt.nodes["Principled BSDF"]
            b.inputs["Metallic"].default_value = 0.7
            ec = _socket(b, "Emission Color", "Emission")
            if ec is not None:
                ec.default_value = hex_rgba(gold)
        except Exception as exc:
            print("governor material:", exc)
        edge_m = self.mat("gov edge " + accent, hex_rgba(accent),
                          roughness=0.3, emission=hex_rgba(accent),
                          strength=0.6)
        me = _dodeca_mesh(self.bpy, tag + ".dodeca", r)
        body = self.obj(tag + ".body", me, spin, face_m)
        body.rotation_euler = (math.radians(31.7), 0, math.radians(12))
        bev = body.modifiers.new("round", "BEVEL")
        bev.width = r * 0.04
        bev.segments = 2
        wire_me = _dodeca_mesh(self.bpy, tag + ".edges", r * 1.01)
        wire = self.obj(tag + ".edges", wire_me, spin, edge_m)
        wire.rotation_euler = body.rotation_euler
        wm = wire.modifiers.new("edges", "WIREFRAME")
        wm.thickness = r * 0.045
        wm.use_replace = True
        return [body, wire], spin, pulse, face_m

    def build_cutout(self, plan, root, tag):
        """Extrude the Manim outline: filled shapes become thin solids,
        strokes become round tubes; later parts sit closer to the camera
        (Manim draws them on top)."""
        bpy = self.bpy
        geo = plan.rec.get("geometry") or {}
        parts = geo.get("parts") or []
        out = []
        merge = len(parts) > 24
        groups = {}
        for i, p in enumerate(parts):
            if p["fill_opacity"] >= 0.2:
                groups.setdefault(("fill", p["fill"]) if merge else
                                  ("fill", i), []).append((i, p))
            if p["stroke_width"] > 0 and p["stroke_opacity"] >= 0.2:
                groups.setdefault(("stroke", p["stroke"], p["stroke_width"])
                                  if merge else ("stroke", i), []).append((i, p))
        n = max(len(parts), 1)
        for key, items in groups.items():
            kind = key[0]
            cu = bpy.data.curves.new(f"{tag}.{kind}", "CURVE")
            cu.dimensions = "2D" if kind == "fill" else "3D"
            if kind == "fill":
                cu.fill_mode = "BOTH"
                cu.extrude = 0.012
                color = items[0][1]["fill"]
            else:
                cu.bevel_depth = max(items[0][1]["stroke_width"] * 0.005, 0.004)
                cu.bevel_resolution = 2
                if hasattr(cu, "use_fill_caps"):
                    cu.use_fill_caps = True
                color = items[0][1]["stroke"]
            for _, p in items:
                for flat in p["paths"]:
                    self._add_spline(cu, flat, closed_only=(kind == "fill"))
            if not cu.splines:
                bpy.data.curves.remove(cu)
                continue
            order = min(i for i, _ in items)
            ob = bpy.data.objects.new(f"{tag}.{kind}", cu)
            self.col.objects.link(ob)
            ob.parent = root
            ob.rotation_euler = (math.pi / 2, 0, 0)
            ob.location = (0, -0.03 * order / n - (0.004 if kind == "stroke"
                                                   else 0.0), 0)
            cu.materials.append(self.mat("cut " + color, hex_rgba(color),
                                         roughness=0.55))
            out.append(ob)
        return out

    @staticmethod
    def _add_spline(cu, flat, closed_only=False):
        pts = [(flat[k], flat[k + 1]) for k in range(0, len(flat) - 1, 2)]
        nseg = len(pts) // 4
        if nseg == 0:
            return
        segs = [pts[4 * s:4 * s + 4] for s in range(nseg)]
        anchors = [segs[0][0]] + [s[3] for s in segs]
        closed = math.hypot(anchors[0][0] - anchors[-1][0],
                            anchors[0][1] - anchors[-1][1]) < 1e-3
        if closed_only and not closed:
            return
        if closed:
            anchors = anchors[:-1]
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(anchors) - 1)
        for k, bp in enumerate(sp.bezier_points):
            bp.co = (anchors[k][0], anchors[k][1], 0.0)
            right = segs[k][1] if k < nseg else anchors[k]
            if k > 0:
                left = segs[k - 1][2]
            elif closed:
                left = segs[-1][2]
            else:
                left = anchors[0]
            bp.handle_left_type = bp.handle_right_type = "FREE"
            bp.handle_left = (left[0], left[1], 0.0)
            bp.handle_right = (right[0], right[1], 0.0)
        sp.use_cyclic_u = closed

    # ── animation ───────────────────────────────────────────────────────
    def visibility(self, objs, rec):
        changes, cur = [], False
        for t, on, _ in rec.get("visibility", []):
            if bool(on) != cur:
                changes.append((t, bool(on)))
                cur = bool(on)
        if changes and changes[0][0] <= 1e-6:
            seq = changes
        else:
            seq = [(0.0, False)] + changes
        key_visibility(objs, seq, self.opt.fps)

    def governor_anim(self, plan, spin, mat, bubbles):
        """Spin (slower in low power), gold/amber color, and a glow that
        flares word by word while the Governor speaks."""
        bpy, opt = self.bpy, self.opt
        rec = plan.rec
        g = rec.get("governor") or {}
        gold = hex_rgba(g.get("gold") or "#e8c547")
        amber = hex_rgba(g.get("amber") or "#d47b00")
        vis = [(t, on) for t, on, _ in rec.get("visibility", [])]
        t_on = next((t for t, on in vis if on), 0.0)
        t_off = next((t for t, on in vis if not on and t > t_on),
                     self.T["duration"])
        traced = [(t, r) for t, r in g.get("spin", []) if r > 0]
        want = plan.spec.get("animate", "spin") == "spin"
        base = traced[0][1] if traced else (SPIN_DEFAULT if want else 0.0)
        states = [(t, s) for t, s in g.get("states", []) if s]
        if not states:
            states = [(t_on, "gold")]

        def state_at(t):
            s = "gold"
            for ts, st in states:
                if ts <= t + 1e-6:
                    s = st
            return s

        def ramp_end(t):
            for m in g.get("moves", []):
                if abs(m["t0"] - t) < 1e-3 and m["t1"] > m["t0"]:
                    return m["t1"]
            return t + 0.4
        # spin: constant rate within each state
        rk = KeyList(opt.fps)
        ang = 0.0
        pts = sorted({t_on, t_off} | {t for t, _ in states if t_on < t < t_off})
        rk.add(0.0, [0.0])
        for a, b in zip(pts[:-1], pts[1:]):
            rk.add(a, [ang])
            st = state_at(a)
            rate = base * (AMBER_SPIN if st == "amber" else
                           0.0 if st == "dark" else 1.0)
            ang += rate * (b - a)
            rk.add(b, [ang])
        apply_keys(bpy, spin, "rotation_euler", [(2, 0, lambda v: v)], rk)
        # glow: strength and color, keyed on the face material
        nt = getattr(mat, "node_tree", None)
        if nt is None:
            return
        b = nt.nodes.get("Principled BSDF")
        names = [i.name for i in b.inputs]
        si = next((k for k, n in enumerate(names)
                   if n == "Emission Strength"), None)
        ci = next((k for k, n in enumerate(names)
                   if n in ("Emission Color", "Emission")), None)
        bi = names.index("Base Color")
        if si is None or ci is None:
            return
        idle = {"gold": 0.7, "amber": 0.3, "dark": 0.0}
        sl = []                       # (t, strength), sorted below
        ck = KeyList(opt.fps)
        sl.append((0.0, idle["gold"]))
        ck.add(0.0, list(gold[:3]))
        prev = "gold"
        for t, st in states:
            if st == prev:
                continue
            t1 = ramp_end(t)
            sl.append((t, idle[prev]))
            sl.append((t1, idle[st]))
            ck.add(t, list((gold if prev != "amber" else amber)[:3]))
            ck.add(t1, list((gold if st != "amber" else amber)[:3]))
            prev = st
        # speaking: one flare per word over the bubble's time on screen
        name = rec["name"]
        flares = []
        for bb in bubbles:
            if bb.get("owner") != name:
                continue
            rows = bb.get("visibility") or []
            for k, (t, on) in enumerate(rows):
                if on:
                    t_end = rows[k + 1][0] if k + 1 < len(rows) else t + 1.5
                    flares.append((t, t_end, max(1, len(bb["text"].split()))))
        for ta, tb, nw in sorted(flares):
            st = state_at(ta)
            lo = idle[st]
            hi = lo + (1.6 if st == "gold" else 0.8)
            beat = max((tb - ta) / nw, 0.12)
            t = ta
            sl.append((ta, lo))
            k = 0
            while t + beat <= tb + 1e-6:
                sl.append((t + beat * 0.35, hi if k % 2 == 0 else hi * 0.8))
                sl.append((t + beat, lo + (hi - lo) * 0.35))
                t += beat
                k += 1
            sl.append((tb, lo))
        sk = KeyList(opt.fps)
        for t, v in sorted(sl, key=lambda e: e[0]):
            sk.add(t, [v], ("SINE", "EASE_IN_OUT"))
        apply_keys(bpy, nt, f'nodes["{b.name}"].inputs[{si}].default_value',
                   [(0, 0, lambda v: v)], sk)
        for path_i in (ci, bi):
            apply_keys(bpy, nt, f'nodes["{b.name}"].inputs[{path_i}].default_value',
                       [(0, 0, lambda v: v), (1, 1, lambda v: v),
                        (2, 2, lambda v: v)], ck)

    def build(self, bubbles, empties):
        T, opt = self.T, self.opt
        sched = floor_schedule(T)
        if not sched:
            g = ground_level(T)
            sched = [(0.0, g)] if g is not None else []
        recs = [r for r in T.get("prop_objects", []) if _visible_from(r)
                is not None]
        plans = [PropPlan(r, sched) for r in recs]
        # unparented props resting on a snapped table/desk share its lift
        for p in plans:
            if p.kind in ("desk", "table", "door", "chair") or p.rec.get("parents"):
                continue
            for q in plans:
                if q.kind in ("desk", "table") and abs(q.dz) > 1e-6 and \
                        abs(p.bottom - q.top_manim) < 0.25 and \
                        abs(p.rec["initial"][0] - (q.meta.get("x", q.cx))) < q.w / 2:
                    p.dz, p.depth = q.dz, q.rest_y()
        joints_of = {n: set(i["joints"]) for n, i in T["cast"].items()}
        stats = {}
        for plan in plans:
            rec = plan.rec
            tag = f"prop.{rec['name']}.{rec['id']}"
            root = self.bpy.data.objects.new(tag, None)
            root.empty_display_size = 0.15
            self.col.objects.link(root)
            k = plan.kind
            gov = None
            if k in ("desk", "table"):
                parts = self.build_desk(plan, root, tag)
            elif k == "door":
                parts = self.build_door(plan, root, tag)
            elif k == "chair":
                parts = self.build_chair(plan, root, tag)
            elif k == "phone":
                parts = self.build_phone(plan, root, tag)
            elif k in ("governor", "dodecahedron"):
                parts, spin, pulse, fmat = self.build_governor(plan, root, tag)
                gov = (spin, pulse, fmat)
            else:
                parts = self.build_cutout(plan, root, tag)
            keys, cons = prop_keys(plan, plans, T, self.rates, opt,
                                   self.native, joints_of)
            for ci, (char, joint) in enumerate(cons):
                c = root.constraints.new("COPY_LOCATION")
                c.name = f"hold {char}.{joint}"
                c.target = empties[char][joint]
                c.use_offset = True
                c.use_y = False
                apply_keys(self.bpy, root,
                           f'constraints["{c.name}"].influence',
                           [(0, 5 + ci, lambda v: v)], keys)
            apply_keys(self.bpy, root, "location",
                       [(0, 0, lambda v: v), (1, 1, lambda v: v),
                        (2, 2, lambda v: v)], keys)
            if any(abs(v[3]) > 1e-6 for v in keys.v):
                apply_keys(self.bpy, root, "rotation_euler",
                           [(0, 3, lambda v: v)], keys)
            if gov is not None:
                # the speaking pulse scales the shape, not the whole rig
                apply_keys(self.bpy, gov[1], "scale",
                           [(i, 4, lambda v: v) for i in range(3)], keys)
                self.governor_anim(plan, gov[0], gov[2], bubbles)
            elif k == "cutout" and any(abs(v[4] - 1) > 1e-3 for v in keys.v):
                apply_keys(self.bpy, root, "scale",
                           [(i, 4, lambda v: v) for i in range(3)], keys)
            for o in parts:
                if hasattr(o, "visible_shadow") and k == "cutout" and \
                        plan.type in BACK_TYPES:
                    o.visible_shadow = False
            self.visibility(parts, rec)
            stats[tag] = {"kind": k, "keys": len(keys.f),
                          "holds": len(rec.get("holds", [])),
                          "dz": round(plan.dz, 3)}
        return stats


def build_props(bpy, sc, T, rates, opt, native, empties):
    if not T.get("prop_objects"):
        return {}
    return PropBuilder(bpy, sc, T, rates, opt, native).build(
        T.get("bubbles") or [], empties)


def build(trace_path, out_path, opt=None):
    import bpy
    opt = opt or Options()
    T = load_trace(trace_path)
    rates = load_rates(T)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = opt.fps
    sc.frame_start = 1
    sc.frame_end = int(math.ceil(1 + T["duration"] * opt.fps))
    sc.render.resolution_x, sc.render.resolution_y = opt.res
    native = verify_native(bpy, rates, opt)

    # world / background color (sRGB hex from Manim -> linear)
    world = bpy.data.worlds.new("World")
    sc.world = world
    if bpy.app.version < (5, 0, 0):              # always on in Blender 5+
        world.use_nodes = True
    bgs = T.get("background") or [[0.0, "#000000"]]
    for k, (t, hx) in enumerate(bgs):
        rgb = hex_rgba(hx)[:3]
        world.color = rgb
        try:
            world.node_tree.nodes["Background"].inputs["Color"].default_value = rgb + (1.0,)
        except Exception:
            pass
        if len(bgs) > 1:
            world.keyframe_insert("color", frame=1.0 if k == 0 else 1 + t * opt.fps)
    if len(bgs) > 1 and world.animation_data:
        for fc in _fcurves(world.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    bg_rgb = hex_rgba(bgs[0][1])[:3]

    setup_look(bpy, sc, T, opt, bg_rgb)
    try:
        sc.view_settings.view_transform = "Standard"   # keep Manim's colors
    except Exception:
        pass

    # Render straight to an H.264 MP4 next to the .blend (Blender 3.x-5.x).
    im = sc.render.image_settings
    if "media_type" in im.bl_rna.properties:      # Blender 5.x
        im.media_type = "VIDEO"
    else:                                         # Blender 3.x / 4.x
        im.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    stem = os.path.splitext(os.path.basename(out_path))[0]
    sc.render.filepath = "//" + stem + "_"     # "//" = folder of the .blend

    # orthographic camera tracking the Manim frame; tilted down a little
    # (except in the flat look) so the floor and the shadows read as 3D
    tilt = 0.0 if opt.look == "flat" else math.radians(opt.tilt)
    cd = bpy.data.cameras.new("Cam")
    cd.type = "ORTHO"
    cd.clip_end = 1000.0
    cam = bpy.data.objects.new("Cam", cd)
    cam.rotation_euler = (math.pi / 2 - tilt, 0, 0)
    ylift = CAM_DIST * math.sin(tilt)
    cam.location = (0.0, -CAM_DIST * math.cos(tilt), ylift)
    sc.collection.objects.link(cam)
    sc.camera = cam
    ck = assemble_camera(T, rates, opt, native)
    apply_keys(bpy, cam, "location",
               [(0, 0, lambda v: v), (2, 1, lambda v: v + ylift)], ck)
    apply_keys(bpy, cd, "ortho_scale", [(0, 2, lambda v: v)], ck)

    bone_me = unit_bone_mesh(bpy)
    ball_me = unit_ball_mesh(bpy)
    stats = {}
    all_empties = {}
    for name, info in T["cast"].items():
        joints = info["joints"]
        if name not in T["initial"] or not T["initial"][name]:
            continue
        sf = figure_scale(T, name)
        col = bpy.data.collections.new(name)
        sc.collection.children.link(col)
        mat = material(bpy, f"{name}_mat", hex_rgba(info["color"]))
        root = bpy.data.objects.new(f"{name}", None)
        col.objects.link(root)
        keys, nbake = assemble_character(name, T, rates, opt, native)
        stats[name] = {"keys": len(keys.f), "baked": nbake}
        is_dog = info.get("class") == "DogGraph"
        chest = has_chest(joints, opt.look) and not is_dog
        female = is_female(name, info, opt) if chest else False
        if chest and not female and abs(opt.hips - 1.0) > 1e-6:
            narrow_hips(keys, joints, opt.hips)
        # skin (head, neck, arms, legs) vs clothing (chest, shoulders, hips)
        skin_hex = opt.skin.get(name) or info.get("skin")
        skin = mat
        if skin_hex and opt.look != "flat":
            skin = material(bpy, f"{name}_skin", hex_rgba(skin_hex))
            stats[name]["skin"] = skin_hex
        # joint ball radius = thickest bone meeting it (rounded joints)
        jr = {}
        for a, b in info["edges"]:
            r = edge_radius(a, b, sf, opt.look)
            jr[a] = max(jr.get(a, 0), r)
            jr[b] = max(jr.get(b, 0), r)
        empties, meshes = {}, []
        for ji, j in enumerate(joints):
            e = bpy.data.objects.new(f"{name}.{j}", None)
            e.empty_display_size = 0.08
            e.parent = root
            col.objects.link(e)
            empties[j] = e
            all_empties.setdefault(name, {})[j] = e
            apply_keys(bpy, e, "location",
                       [(0, 2 * ji, lambda v: v), (2, 2 * ji + 1, lambda v: v)],
                       keys)
            if chest and j in INNER_JOINTS:
                continue                  # hidden inside the chest
            if j == "head":
                r = (info.get("head_radius", 0.28) if opt.look == "flat"
                     else HEAD_R * sf)
            else:
                r = JOINT_R if opt.look == "flat" else jr.get(j, LIMB_R * sf)
                if opt.look != "flat" and j in HINGES:
                    r *= HINGE_SCALE
            ball = bpy.data.objects.new(f"{name}.{j}.ball", ball_me)
            col.objects.link(ball)
            ball.material_slots[0].link = "OBJECT"
            ball.material_slots[0].material = mat if (
                j in CLOTHED_JOINTS or (not chest and j in INNER_JOINTS)) \
                else skin
            ball.parent = e
            ball.location = (0, 0, 0)
            ball.scale = (r, r, r)
            meshes.append(ball)
        if chest and keys.f:
            CV = chest_corner_values(np.array(keys.v), joints, female, sf)
            ck = KeyList(opt.fps)
            ck.f, ck.v, ck.spec = list(keys.f), list(CV), list(keys.spec)
            corners = {}
            for ci, c in enumerate(CHEST_CORNERS):
                e = bpy.data.objects.new(f"{name}.chest.{c}", None)
                e.empty_display_size = 0.05
                e.parent = root
                col.objects.link(e)
                corners[c] = e
                apply_keys(bpy, e, "location",
                           [(0, 2 * ci, lambda v: v), (2, 2 * ci + 1, lambda v: v)],
                           ck)
            meshes.append(build_chest(bpy, col, name, corners, mat, sf, female))
            if female and opt.bust:
                bk = KeyList(opt.fps)
                bk.f, bk.v, bk.spec = list(keys.f), list(bust_values(CV)), list(keys.spec)
                for bi, side in enumerate(("l", "r")):
                    e = bpy.data.objects.new(f"{name}.bust.{side}", None)
                    e.empty_display_size = 0.05
                    e.parent = root
                    col.objects.link(e)
                    apply_keys(bpy, e, "location",
                               [(0, 2 * bi, lambda v: v), (2, 2 * bi + 1, lambda v: v)],
                               bk)
                    ball = bpy.data.objects.new(f"{name}.bust.{side}.ball", ball_me)
                    col.objects.link(ball)
                    ball.material_slots[0].link = "OBJECT"
                    ball.material_slots[0].material = mat
                    ball.parent = e
                    rb = BUST_R * sf
                    # sits on the chest's front face, flattened front-to-back
                    ball.location = (0, -CHEST_DEPTH * sf / 2, 0)
                    ball.scale = (rb, rb * 0.75, rb * 0.9)
                    meshes.append(ball)
            stats[name]["chest"] = "female" if female else "male"
        for a, b in info["edges"]:
            if a not in empties or b not in empties:
                continue
            if chest and is_torso_edge(a, b):
                continue
            ob = bpy.data.objects.new(f"{name}.{a}-{b}", bone_me)
            col.objects.link(ob)
            ob.material_slots[0].link = "OBJECT"
            clothed = {a, b} & (TORSO_JOINTS - {"neck"}) or \
                {a, b} in ({"neck", "lshoulder"}, {"neck", "rshoulder"},
                           {"lhip", "rhip"}, {"lshoulder", "rshoulder"})
            ob.material_slots[0].material = mat if clothed else skin
            r = edge_radius(a, b, sf, opt.look)
            ob.scale = (r, 1.0, r)
            c1 = ob.constraints.new("COPY_LOCATION")
            c1.target = empties[a]
            c2 = ob.constraints.new("STRETCH_TO")
            c2.target = empties[b]
            c2.rest_length = 1.0
            c2.volume = "NO_VOLUME"
            meshes.append(ob)
        if opt.shoes and opt.look != "flat" and not is_dog:
            meshes += build_shoes(bpy, col, name, empties, sf,
                                  material(bpy, f"{name}_shoes",
                                           hex_rgba(opt.shoes), roughness=0.3),
                                  ball_me, T, opt.fps)
        # visibility: sparse keys, only where it changes
        rows = T["visibility"].get(name, [])
        changes, cur = [], False
        for t, on, _op in rows:
            if bool(on) != cur:
                changes.append((t, bool(on)))
                cur = bool(on)
        first_on = changes[0][0] if changes and changes[0][1] else None
        seq = [(0.0, False)] if first_on is None or first_on > 0 else []
        seq += changes
        key_visibility(meshes, seq, opt.fps)
        stats[name]["vis_keys"] = len(seq)

    pstats = build_props(bpy, sc, T, rates, opt, native, all_empties) \
        if opt.props else {}
    nb = build_bubbles(bpy, sc, T, rates, opt, native, tilt) if opt.bubbles else 0

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_path))
    print(f"wrote {out_path}: {len(T['cast'])} characters, {len(pstats)} props, "
          f"{nb} speech bubbles, "
          f"{sc.frame_end} frames @ {opt.fps} fps, look={opt.look}, "
          f"engine={sc.render.engine} (trace v{T.get('trace_version', 1)})")
    print("native easings:", {k: (v[0], v[1], round(v[2], 4))
                              for k, v in native.items()})
    print("keys:", stats)
    if pstats:
        print("props:", pstats)
    return stats


if __name__ == "__main__":
    tp, op, o = parse_args(sys.argv)
    build(tp, op, o)
