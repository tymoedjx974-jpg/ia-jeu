"""Vidéo de démonstration des mouvements du plugin TMMouvements (Toits Morts), rendue dans Blender.

Un mannequin parcourt un petit parcours provençal et enchaîne les mouvements du joueur, avec les valeurs par défaut des
composants TM Movement et TM Parkour : marche 3,1 m/s, sprint 5,6 m/s, glissade (départ 5,6 + 1 m/s, freinage 3,6 m/s²
jusqu'à 2 m/s), franchissement d'un muret, saut (4,2 m/s vers le haut), escalade d'un rebord de 2,20 m
(durée 0,35 + H/4,8 s), échelle à 1,7 m/s, chute de 5,4 m amortie par une roulade de 0,6 s, marche accroupie à 1,7 m/s,
coup de pied de face (0,56 s, impact à 0,25 s).

Usage (dans le dossier de travail qui contient tex/) :
  python video_mouvements.py            -> images dans video/ puis video/mouvements.mp4
  python video_mouvements.py test 120   -> une seule image (la 120e) pour régler la scène
"""
import sys, os, math, json, subprocess
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, mathutils
from geomlib import MB, box, tube, revolve
from trees import catalog

FPS = 25
G = 9.8
D2R = math.pi / 180.0

# ------------------------------------------------------------------ valeurs du plugin (TMMovementComponent.h, TMParkourComponent.h)
WALK, SPRINT, CROUCH = 3.1, 5.6, 1.7
SLIDE_BOOST, SLIDE_FRICTION, SLIDE_END = 1.0, 3.6, 2.0
JUMP_V = 4.2
ROLL_DUR = 0.6
CLIMB = 1.7
KICK_DUR, KICK_HIT = 0.56, 0.25
L_THIGH, L_SHIN, FOOT_H = 0.45, 0.45, 0.07
STAND_Z = L_THIGH + L_SHIN + FOOT_H


# ------------------------------------------------------------------ poses
def pose(**kw):
    p = dict(lean=0.0, hipL=0.0, hipR=0.0, kneeL=0.0, kneeR=0.0, shL=0.0, shR=0.0, elbL=10.0, elbR=10.0,
             abdL=6.0, abdR=6.0, hipAbdL=0.0, hipAbdR=0.0, head=0.0, pitch=0.0, yaw=0.0, roll=0.0)
    p.update(kw)
    return p


def mix(a, b, t):
    t = min(1.0, max(0.0, t))
    return {k: a[k] * (1 - t) + b[k] * t for k in a}


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def gait(phi, v, crouch=False):
    """Cycle de marche / course selon la vitesse ; phi en radians."""
    r = min(1.0, max(0.0, (v - 2.0) / 3.6))           # 0 marche, 1 sprint
    if crouch:
        A, kmin, ksw, lean, Aa, e0 = 22.0, 70.0, 45.0, 28.0, 14.0, 60.0
        base = 45.0
    else:
        A = 24 + 22 * r
        kmin, ksw = 8 + 10 * r, 45 + 60 * r
        lean = 3 + 13 * r
        Aa, e0 = 22 + 28 * r, 18 + 70 * r
        base = 4 * r
    c = math.cos(phi)
    kR = kmin + ksw * max(0.0, c) ** 1.3 + 12 * max(0.0, -c) * r
    kL = kmin + ksw * max(0.0, -c) ** 1.3 + 12 * max(0.0, c) * r
    return pose(lean=lean, hipR=base + A * math.sin(phi), hipL=base - A * math.sin(phi), kneeR=kR, kneeL=kL,
                shR=-Aa * math.sin(phi), shL=Aa * math.sin(phi), elbR=e0 + 10 * max(0, -math.sin(phi)),
                elbL=e0 + 10 * max(0, math.sin(phi)), head=-lean * 0.6)


def stride(v, crouch=False):
    return 1.0 if crouch else 0.9 + 0.55 * v


def foot_min(p):
    """Hauteur du pied le plus bas sous le bassin (plan sagittal)."""
    zs = []
    for s in ("L", "R"):
        h, k = p["hip" + s] * D2R, p["knee" + s] * D2R
        zs.append(-L_THIGH * math.cos(h) - L_SHIN * math.cos(h - k))
    return min(zs) - FOOT_H


STAND = pose()
SLIDE = pose(lean=-38, hipR=78, kneeR=8, hipL=35, kneeL=105, shR=-35, elbR=10, abdR=30, shL=55, elbL=40, head=30)
TUCK = pose(lean=48, hipR=115, hipL=115, kneeR=135, kneeL=135, shR=60, shL=60, elbR=110, elbL=110, head=-35)
CROUCH_IDLE = pose(lean=22, hipR=62, hipL=62, kneeR=105, kneeL=105, shR=25, shL=25, elbR=60, elbL=60, head=-15)
AIR = pose(lean=8, hipR=55, kneeR=55, hipL=-18, kneeL=75, shR=-30, shL=70, elbR=40, elbL=30, head=-5)
FALL = pose(lean=5, hipR=25, kneeR=40, hipL=10, kneeL=30, shR=120, shL=120, abdR=55, abdL=55, elbR=25, elbL=25, head=-15)
LAND = pose(lean=25, hipR=65, hipL=65, kneeR=100, kneeL=100, shR=30, shL=30, elbR=40, elbL=40, head=-10)
VAULT = pose(lean=18, hipR=80, kneeR=100, hipL=95, kneeL=115, shR=35, elbR=0, abdR=10, shL=80, elbL=20, abdL=30,
             hipAbdR=-25, hipAbdL=-15, roll=-25, head=-10)
REACH = pose(lean=-4, hipR=10, kneeR=15, hipL=0, kneeL=10, shR=172, shL=172, elbR=8, elbL=8, head=20)
PULL = pose(lean=35, hipR=95, kneeR=120, hipL=15, kneeL=30, shR=-15, shL=-15, elbR=5, elbL=5, head=-10)
KICK = pose(lean=-14, hipR=92, kneeR=5, hipL=0, kneeL=15, shR=45, shL=65, elbR=100, elbL=100, head=5)
KICK_LOAD = pose(lean=5, hipR=85, kneeR=110, hipL=0, kneeL=15, shR=45, shL=60, elbR=100, elbL=100)
ZOMBIE = pose(lean=12, hipR=8, hipL=-4, kneeR=15, kneeL=12, shR=80, shL=72, elbR=15, elbL=25, abdR=10, abdL=14, head=-12)


# ------------------------------------------------------------------ séquence (simulation image par image)
class Sim:
    def __init__(self):
        self.frames = []
        self.x, self.lvl, self.phi, self.v = 0.0, 0.0, 0.0, 0.0
        self.marks = {}
        self.zombie = []          # (frame, angle de chute)
        self.last = STAND

    def emit(self, p, z=None, label="", key="", show_v=None, pivot=None):
        """z : hauteur du bassin imposée (en l'air) ; sinon posé au sol. pivot : (x, z, angle) pour la roulade."""
        g = z is None
        if z is None:
            z = self.lvl - foot_min(p)
        self.frames.append(dict(x=self.x, z=z, p=p, label=label, key=key, v=self.v if show_v is None else show_v, pivot=pivot,
                                phi=self.phi, ground=g))
        self.last = p

    def run(self, dur, v0, v1, label, key, crouch=False, blend_from=None, blend_t=0.2):
        n = int(round(dur * FPS))
        for i in range(n):
            t = (i + 0.5) / max(1, n)
            self.v = v0 + (v1 - v0) * smooth(t) if v1 != v0 else v0
            self.x += self.v / FPS
            self.phi += 2 * math.pi * self.v / stride(self.v, crouch) / FPS
            p = gait(self.phi, max(self.v, 0.01), crouch)
            if self.v < 0.3 and not crouch:
                p = mix(p, STAND, 1 - self.v / 0.3)
            if blend_from is not None and i < blend_t * FPS:
                p = mix(blend_from, p, smooth(i / (blend_t * FPS)))
            self.emit(p, label=label, key=key)

    def hold(self, dur, p, label, key="", breathe=True):
        n = int(round(dur * FPS))
        for i in range(n):
            q = dict(p)
            if breathe:
                q["lean"] += 1.2 * math.sin(i / FPS * 2.4)
            self.v = 0.0
            self.emit(q, label=label, key=key)

    def blend(self, dur, a, b, label, key="", v=None):
        n = int(round(dur * FPS))
        for i in range(n):
            if v is not None:
                self.v = v
                self.x += v / FPS
            self.emit(mix(a, b, smooth((i + 1) / n)), label=label, key=key)


def build_sequence():
    S = Sim()
    S.hold(1.2, STAND, "TM Mouvements", "")
    S.run(0.6, 0.0, WALK, "Marche", "Z Q S D")
    S.run(2.2, WALK, WALK, "Marche", "Z Q S D")
    S.run(0.8, WALK, SPRINT, "Sprint : élan progressif", "Maj")
    S.run(1.6, SPRINT, SPRINT, "Sprint", "Maj")
    # glissade
    S.marks["slide"] = S.x
    v = SPRINT + SLIDE_BOOST
    dur = (v - SLIDE_END) / SLIDE_FRICTION
    n = int(round(dur * FPS))
    for i in range(n):
        t = (i + 0.5) / FPS
        S.v = v - SLIDE_FRICTION * t
        S.x += S.v / FPS
        p = mix(S.last, SLIDE, smooth(i / (0.18 * FPS))) if i < 0.18 * FPS else SLIDE
        S.emit(p, label="Glissade", key="C en courant")
    S.marks["slide_end"] = S.x
    S.blend(0.3, SLIDE, gait(S.phi, 2.5), "Glissade : on se relève", "C", v=2.2)
    S.run(1.1, 2.2, SPRINT, "Sprint", "Maj")
    S.run(0.35, SPRINT, SPRINT, "Sprint", "Maj")
    # franchissement d'un muret
    d = 2.8
    vd = min(0.75, max(0.35, d / SPRINT * 1.1))
    x0 = S.x
    S.marks["wall"] = x0 + 1.35
    z0 = S.lvl + STAND_Z - 0.05
    zo = 1.0 + 0.62
    n = int(round(vd * FPS))
    for i in range(n):
        t = (i + 1) / n
        S.x = x0 + d * t
        z = (1 - t) ** 2 * z0 + 2 * (1 - t) * t * (zo + 0.35) + t * t * (z0 - 0.1)
        w = math.sin(math.pi * t)
        S.emit(mix(gait(S.phi, SPRINT), VAULT, min(1, w * 1.6)), z=z, label="Franchissement automatique", key="(40 à 130 cm)")
    S.blend(0.12, VAULT, gait(S.phi, SPRINT), "Franchissement automatique", "(40 à 130 cm)", v=SPRINT)
    S.run(0.75, SPRINT, SPRINT, "Sprint", "Maj")
    # saut par-dessus le canal
    S.marks["canal"] = S.x + 0.9
    S.blend(0.08, S.last, LAND, "Saut", "Espace", v=SPRINT)
    T = 2 * JUMP_V / G
    n = int(round(T * FPS))
    x0, z0 = S.x, S.lvl + STAND_Z - 0.08
    for i in range(n):
        t = (i + 1) / FPS
        S.x = x0 + SPRINT * t
        z = z0 + JUMP_V * t - 0.5 * G * t * t
        u = t / T
        p = mix(LAND, AIR, smooth(u * 4)) if u < 0.5 else mix(AIR, LAND, smooth((u - 0.7) / 0.3))
        S.emit(p, z=max(z, S.lvl - foot_min(p)), label="Saut : 0,9 m de haut", key="Espace", show_v=SPRINT)
    S.blend(0.15, LAND, gait(S.phi, 4.5), "Saut : réception", "", v=4.5)
    S.run(0.9, 4.5, SPRINT, "Sprint", "Maj")
    S.run(0.55, SPRINT, 2.2, "Escalade", "Espace face au mur")
    # escalade d'un rebord de 2,20 m
    H = 2.2
    S.marks["house"] = S.x + 0.42
    md = 0.35 + H / 4.8
    n = int(round(md * FPS))
    x0, z0 = S.x, S.lvl + STAND_Z
    xt, zt = S.marks["house"] + 0.55, S.lvl + H + STAND_Z
    p_start = S.last
    for i in range(n):
        u = (i + 1) / n
        if u < 0.55:
            a = smooth(u / 0.55)
            S.x = x0
            z = z0 + (zt - 0.55 - z0) * a
            p = mix(p_start, REACH, smooth(u / 0.2)) if u < 0.2 else mix(REACH, PULL, smooth((u - 0.2) / 0.35))
        else:
            a = smooth((u - 0.55) / 0.45)
            S.x = x0 + (xt - x0) * a
            z = zt - 0.55 + 0.55 * a
            p = mix(PULL, STAND, a)
        S.v = 0.0
        S.emit(p, z=z, label="Escalade : attraper le rebord et se hisser", key="jusqu'à 2,30 m")
    S.lvl += H
    S.x = xt
    S.run(0.5, 0.0, WALK, "Course sur les toits", "")
    S.run(1.4, WALK, WALK, "Course sur les toits", "")
    S.run(0.45, WALK, 0.6, "Échelle", "avancer vers l'échelle")
    # échelle
    S.marks["ladder"] = S.x + 0.38
    top = S.lvl + 3.2
    S.marks["tower_top"] = top
    ladder_pose = lambda ph: pose(lean=-2, hipR=45 + 30 * math.sin(ph), kneeR=70 + 40 * math.sin(ph), hipL=45 - 30 * math.sin(ph),
                                  kneeL=70 - 40 * math.sin(ph), shR=150 + 18 * math.sin(ph + 1.4), elbR=35 - 25 * math.sin(ph + 1.4),
                                  shL=150 - 18 * math.sin(ph + 1.4), elbL=35 + 25 * math.sin(ph + 1.4), head=15)
    S.blend(0.25, S.last, ladder_pose(0.0), "Échelle", "", v=0.0)
    z = S.lvl - foot_min(ladder_pose(0.0))
    climb_h = top - 0.35 - S.lvl
    n = int(round(climb_h / CLIMB * FPS))
    ph = 0.0
    for i in range(n):
        ph += 2 * math.pi * CLIMB / 0.6 / FPS
        z += CLIMB / FPS
        S.v = CLIMB
        S.emit(ladder_pose(ph), z=z, label="Échelle : 1,7 m/s", key="avancer = monter", show_v=CLIMB)
    # en haut : on se hisse sur la tour
    x0, z0 = S.x, z
    xt, zt = S.marks["ladder"] + 0.6, top + STAND_Z
    n = int(round(0.7 * FPS))
    for i in range(n):
        u = (i + 1) / n
        S.x = x0 + (xt - x0) * smooth(max(0, (u - 0.35) / 0.65))
        zz = z0 + (zt - z0) * smooth(min(1, u / 0.7))
        p = mix(ladder_pose(ph), PULL, smooth(u / 0.4)) if u < 0.5 else mix(PULL, STAND, smooth((u - 0.5) / 0.5))
        S.v = 0.0
        S.emit(p, z=zz, label="Échelle : on se hisse en haut", key="")
    S.lvl = top
    S.x = xt
    S.run(1.2, 0.0, 5.0, "Élan sur la tour", "Maj")
    S.marks["tower_edge"] = S.x + 0.25
    # saut dans le vide, chute de 5,4 m
    x0, z0 = S.x, S.lvl + STAND_Z
    vx = 5.0
    t = 0.0
    fall_frames = []
    while True:
        t += 1.0 / FPS
        z = z0 + JUMP_V * t - 0.5 * G * t * t
        if z <= STAND_Z * 0.62 and t > 0.3:
            break
        fall_frames.append((t, z))
    Tf = fall_frames[-1][0]
    for t, z in fall_frames:
        S.x = x0 + vx * t
        u = t / Tf
        if u < 0.25:
            p = mix(gait(S.phi, 5.0), AIR, smooth(u / 0.25))
        elif u < 0.85:
            p = mix(AIR, FALL, smooth((u - 0.25) / 0.25))
        else:
            p = mix(FALL, TUCK, smooth((u - 0.85) / 0.15))
        vz = JUMP_V - G * t
        S.v = vx
        S.emit(p, z=z, label="Chute de 5,4 m", key="C juste avant l'impact", show_v=math.hypot(vx, vz))
    S.marks["land"] = S.x
    S.lvl = 0.0
    # roulade : aucun dégât, on garde l'élan
    n = int(round(ROLL_DUR * FPS))
    vr = max(vx, 4.2)
    for i in range(n):
        u = (i + 1) / n
        S.x += vr / FPS
        ang = 360.0 * (u * u * (3 - 2 * u))
        S.v = vr
        S.emit(TUCK if 0.1 < u < 0.85 else mix(TUCK, gait(S.phi, 4.0), smooth((u - 0.85) / 0.15)) if u >= 0.85 else TUCK,
               z=0.52, label="Roulade : aucun dégât", key="C", pivot=(S.x, 0.5, ang))
    S.run(1.0, 4.2, 4.2, "Course", "")
    S.run(0.5, 4.2, CROUCH, "Accroupi", "C", crouch=False)
    S.marks["passage"] = S.x + 0.8
    S.run(3.4, CROUCH, CROUCH, "Accroupi : 1,7 m/s", "C", crouch=True, blend_from=S.last, blend_t=0.35)
    S.blend(0.35, S.last, gait(S.phi, 2.0), "Accroupi : on se relève", "", v=1.8)
    S.run(0.7, 1.8, WALK, "Marche", "")
    S.run(0.45, WALK, 0.0, "Coup de pied", "A")
    S.marks["zombie"] = S.x + 1.05
    # coup de pied de face
    n = int(round(KICK_DUR * FPS))
    hit = int(round(KICK_HIT * FPS))
    for i in range(n):
        u = (i + 1) / n
        if u < KICK_HIT / KICK_DUR:
            p = mix(STAND, KICK_LOAD, smooth(u / (KICK_HIT / KICK_DUR) * 1.6)) if u < 0.28 else mix(KICK_LOAD, KICK, smooth((u - 0.28) / 0.17))
        else:
            p = mix(KICK, STAND, smooth((u - 0.45) / 0.55))
        S.v = 0.0
        S.emit(p, label="Coup de pied", key="A")
        if i == hit:
            S.marks["hit_frame"] = len(S.frames)
    S.hold(1.8, STAND, "Coup de pied", "A")
    S.hold(1.4, STAND, "TM Mouvements", "")
    return S


# ------------------------------------------------------------------ mannequin articulé
SKIN = (196, 160, 132, 255)


def capsule(mb, mat, length, r0, r1, col, segs=12):
    """Membre arrondi aux deux bouts, de l'articulation (z = 0, rayon r0) vers le bas (z = -length, rayon r1)."""
    prof = []
    for k in range(5):                       # calotte du bas
        a = -math.pi / 2 + k / 4 * math.pi / 2
        prof.append((r1 * math.cos(a), -length + r1 * math.sin(a)))
    for k in range(5):                       # calotte du haut
        a = k / 4 * math.pi / 2
        prof.append((r0 * math.cos(a), r0 * math.sin(a)))
    prof[0] = (0.0, prof[0][1])
    prof[-1] = (0.0, prof[-1][1])
    revolve(mb, mat, prof, (0, 0, 0), segs=segs, col=col, u_tile=0.5, v_tile=0.5)


def make_body(prefix, cols):
    """cols : dict veste, pantalon, peau, chaussures. Renvoie le dictionnaire des os (objets Blender)."""
    def obj(name, mb, parent=None, loc=(0, 0, 0)):
        arr = mb.arrays() if mb is not None else {}
        if arr:
            ob = bl.mesh_object(prefix + name, arr)
        else:
            ob = bpy.data.objects.new(prefix + name, None)
            bpy.context.scene.collection.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        ob.location = loc
        ob.rotation_mode = "XYZ"
        return ob
    B = {}
    mb = MB()
    box(mb, "Toile", (0, 0, 0.02), (0.24, 0.34, 0.2), col=cols["pants"], uv_scale=0.5)
    B["root"] = obj("root", None)
    B["pelvis"] = obj("pelvis", mb, B["root"])
    mb = MB()
    box(mb, "Toile", (0, 0, 0.26), (0.24, 0.4, 0.36), col=cols["jacket"], uv_scale=0.5)
    box(mb, "Toile", (0, 0, 0.1), (0.22, 0.34, 0.2), col=cols["jacket"], uv_scale=0.5)
    revolve(mb, "Toile", [(0.0, 0.42), (0.21, 0.42), (0.2, 0.48), (0.0, 0.5)], (0, 0, 0), segs=12, col=cols["jacket"])
    B["spine"] = obj("spine", mb, B["pelvis"], (0, 0, 0.1))
    mb = MB()
    tube(mb, "Peinture", [(0, 0, 0), (0, 0, 0.1)], 0.055, segs=10, col=cols["skin"])
    revolve(mb, "Peinture", [(0.0, 0.06), (0.07, 0.09), (0.1, 0.17), (0.1, 0.24), (0.075, 0.31), (0.0, 0.335)], (0, 0, 0), segs=16,
            col=cols["skin"])
    box(mb, "Toile", (0.02, 0, 0.3), (0.2, 0.2, 0.06), col=cols["hair"], uv_scale=0.5)
    box(mb, "Peinture", (0.095, 0, 0.2), (0.02, 0.1, 0.04), col=(40, 34, 30, 255))     # regard (sens du visage)
    B["head"] = obj("head", mb, B["spine"], (0, 0, 0.48))
    for s, sy in (("L", 1), ("R", -1)):
        mb = MB()
        capsule(mb, "Toile", 0.28, 0.055, 0.048, cols["jacket"])
        B["sh" + s] = obj("sh" + s, mb, B["spine"], (0, sy * 0.24, 0.42))
        mb = MB()
        capsule(mb, "Toile", 0.24, 0.045, 0.04, cols["jacket"])
        box(mb, "Peinture", (0, 0, -0.3), (0.06, 0.09, 0.13), col=cols["skin"])
        B["elb" + s] = obj("elb" + s, mb, B["sh" + s], (0, 0, -0.29))
        mb = MB()
        capsule(mb, "Toile", L_THIGH - 0.04, 0.085, 0.065, cols["pants"])
        B["hip" + s] = obj("hip" + s, mb, B["pelvis"], (0, sy * 0.1, -0.02))
        mb = MB()
        capsule(mb, "Toile", L_SHIN - 0.06, 0.06, 0.05, cols["pants"])
        box(mb, "BoisBrut", (0.05, 0, -L_SHIN - 0.02), (0.27, 0.1, 0.09), col=cols["shoes"])
        B["knee" + s] = obj("knee" + s, mb, B["hip" + s], (0, 0, -L_THIGH))
    return B


def apply_pose(B, p):
    B["spine"].rotation_euler = (0, p["lean"] * D2R, 0)
    B["head"].rotation_euler = (0, p["head"] * D2R, 0)
    for s, sy in (("L", 1), ("R", -1)):
        B["sh" + s].rotation_euler = (sy * p["abd" + s] * D2R, -p["sh" + s] * D2R, 0)
        B["elb" + s].rotation_euler = (0, -p["elb" + s] * D2R, 0)
        B["hip" + s].rotation_euler = (sy * p["hipAbd" + s] * D2R, -p["hip" + s] * D2R, 0)
        B["knee" + s].rotation_euler = (0, p["knee" + s] * D2R, 0)
    B["pelvis"].rotation_euler = (p["roll"] * D2R, p["pitch"] * D2R, p["yaw"] * D2R)


# ------------------------------------------------------------------ décor : un bout de village provençal
def build_set(M):
    mb = MB()
    L = M["zombie"] + 25
    # sol : calade au centre, terre et gravier autour ; le canal coupe le chemin
    c0, c1 = M["canal"], M["canal"] + 3.0
    for a, b in ((-20.0, c0), (c1, L)):
        box(mb, "Calade", ((a + b) / 2, 0, -0.5), (b - a, 5.0, 1.0), uv_scale=2.0)
        for sy in (1, -1):
            box(mb, "Gravier", ((a + b) / 2, sy * 16.25, -0.52), (b - a, 27.5, 1.0), uv_scale=2.0)
    box(mb, "PierreTaille", ((c0 + c1) / 2, 0, -1.6), (3.0, 60.0, 0.4), uv_scale=3.0)
    box(mb, "Eau", ((c0 + c1) / 2, 0, -0.55), (3.0, 60.0, 0.05), col=(120, 140, 150, 255), uv_scale=2.0)
    for x in (c0 + 0.15, c1 - 0.15):
        box(mb, "PierreTaille", (x, 0, -0.45), (0.3, 60.0, 0.95), uv_scale=3.0)
    # barrière de la glissade : une poutre sur deux piquets, à 1,05 m
    xs = M["slide"] + 2.3
    box(mb, "BoisBrut", (xs, 0, 1.12), (0.18, 3.6, 0.16), col=(150, 120, 90, 255))
    for sy in (1.7, -1.7):
        box(mb, "BoisBrut", (xs, sy, 0.6), (0.14, 0.14, 1.25), col=(150, 120, 90, 255))
    box(mb, "Peinture", (xs - 0.1, 0, 1.12), (0.01, 3.4, 0.08), col=(200, 40, 30, 255))
    # muret de pierre sèche (1 m)
    box(mb, "PierreMoellons", (M["wall"], 0, 0.5), (0.5, 6.0, 1.0), uv_scale=3.0)
    box(mb, "PierreTaille", (M["wall"], 0, 1.03), (0.56, 6.1, 0.08), uv_scale=3.0)
    # maison à toit-terrasse de 2,20 m, puis tour de 5,40 m avec son échelle
    xh, xl = M["house"], M["ladder"]
    box(mb, "Enduit", ((xh + xl) / 2, 0, 1.1), (xl - xh, 5.0, 2.2), col=(226, 196, 150, 255), uv_scale=3.0)
    box(mb, "PierreTaille", ((xh + xl) / 2, 0, 2.23), (xl - xh + 0.1, 5.1, 0.06), uv_scale=3.0)
    box(mb, "BoisPeint", (xh - 0.01, 1.6, 0.95), (0.05, 1.0, 1.9), col=(90, 130, 140, 255))
    top = M["tower_top"]
    xe = M["tower_edge"]
    box(mb, "Enduit", ((xl + xe) / 2, 0, top / 2), (xe - xl, 4.0, top), col=(214, 170, 120, 255), uv_scale=3.0)
    box(mb, "PierreTaille", ((xl + xe) / 2, 0, top + 0.03), (xe - xl + 0.1, 4.1, 0.06), uv_scale=3.0)
    for sy in (0.25, -0.25):
        box(mb, "Fer", (xl - 0.08, sy, (2.2 + top + 1.0) / 2), (0.05, 0.05, top + 1.0 - 2.2), col=(70, 70, 72, 255))
    for z in np.arange(2.45, top + 1.0, 0.3):
        box(mb, "Fer", (xl - 0.08, 0, z), (0.035, 0.5, 0.035), col=(70, 70, 72, 255))
    # passage voûté bas (1,50 m) : il faut s'accroupir
    xp = M["passage"]
    box(mb, "PierreMoellons", (xp + 2.4, 1.1, 0.75), (5.0, 0.4, 1.5), uv_scale=3.0)     # mur du fond
    for px in (xp + 0.1, xp + 4.7):                                                          # côté caméra : deux piliers
        box(mb, "PierreMoellons", (px, -1.1, 0.75), (0.5, 0.4, 1.5), uv_scale=3.0)
    box(mb, "PierreMoellons", (xp + 2.4, 0, 1.5 + 0.5), (5.0, 3.0, 1.0), uv_scale=3.0)
    box(mb, "TuilesCanal", (xp + 2.4, 0, 2.56), (5.2, 3.2, 0.12), uv_scale=2.0)
    # façades du village en fond
    rng = np.random.default_rng(3)
    x = -18.0
    tints = [(232, 204, 160, 255), (214, 170, 118, 255), (236, 222, 196, 255), (200, 150, 110, 255), (226, 186, 140, 255)]
    while x < L:
        w = rng.uniform(6, 10)
        h = rng.uniform(6, 10)
        y0 = 11.0 + rng.uniform(0, 2)
        box(mb, "Enduit", (x + w / 2, y0 + 3, h / 2), (w - 0.2, 6, h), col=tints[rng.integers(len(tints))], uv_scale=3.0)
        box(mb, "TuilesCanal", (x + w / 2, y0 + 1.5, h + 0.9), (w + 0.2, 3.6, 0.16), pitch=0.45, uv_scale=2.0)
        box(mb, "TuilesCanal", (x + w / 2, y0 + 4.5, h + 0.9), (w + 0.2, 3.6, 0.16), pitch=-0.45, uv_scale=2.0)
        for k in range(int(w / 2.4)):
            for f in range(int(h / 3)):
                fx = x + 1.2 + k * 2.4
                box(mb, "BoisPeint", (fx, y0 - 0.02, 1.8 + f * 3.0), (0.9, 0.06, 1.4), col=(90, 130, 140, 255) if (k + f) % 3 else (140, 150, 90, 255))
        x += w
    return mb


def main():
    S = build_sequence()
    F = S.frames
    M = S.marks
    print("séquence : %d images, %.1f s, parcours de %.0f m" % (len(F), len(F) / FPS, F[-1]["x"]), flush=True)
    bl.reset()
    bl.setup_world(sun_elev=34.0, sun_azim=215.0, exposure=-0.2)
    test = "test" in sys.argv[1:]
    bl.setup_render(640, 360, samples=4)
    sc = bpy.context.scene
    sc.cycles.max_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.render.fps = FPS
    sc.render.use_persistent_data = True
    bl.mesh_object("Decor", build_set(M).arrays())
    # végétation : cyprès, oliviers, lavande devant les façades
    C = catalog()
    rng = np.random.default_rng(7)
    protos = {}
    def plant(name, x, y, yaw, s=1.0):
        if name not in protos:
            protos[name] = C[name](2)[0].arrays()
        ob = bl.mesh_object(f"{name}_{x:.0f}_{y:.0f}", protos[name], location=(x, y, 0))
        ob.rotation_euler[2] = yaw
        ob.scale = (s, s, s)
    for x in np.arange(-10, M["zombie"] + 20, 16.0):
        plant("Arbre_Cypres_%d" % rng.integers(4), x + rng.uniform(-1, 1), 8.6 + rng.uniform(-0.5, 0.5), 0.0, rng.uniform(0.7, 0.9))
    for x in np.arange(-6, M["zombie"] + 20, 14.0):
        plant("Arbre_Olivier_%d" % rng.integers(4), x, -10 - rng.uniform(0, 4), rng.uniform(0, 6.28), rng.uniform(0.8, 1.0))
    # personnages
    P = make_body("J_", dict(jacket=(62, 84, 120, 255), pants=(58, 56, 54, 255), skin=SKIN, shoes=(60, 45, 35, 255), hair=(50, 38, 30, 255)))
    Z = make_body("Z_", dict(jacket=(96, 104, 80, 255), pants=(74, 66, 58, 255), skin=(150, 160, 130, 255), shoes=(50, 44, 40, 255),
                             hair=(40, 40, 36, 255)))
    Z["root"].rotation_euler = (0, 0, math.pi)
    zx = M["zombie"]
    hitf = M.get("hit_frame", len(F))
    cam = bl.camera((0, -8, 2), (0, 0, 1), lens=30.0, name="CamVideo")
    os.makedirs("video", exist_ok=True)
    frames = range(len(F))
    if test:
        arg = sys.argv[sys.argv.index("test") + 1] if len(sys.argv) > sys.argv.index("test") + 1 else "60"
        frames = [int(a) for a in arg.split(",")]
    # caméra subjective, comme TM Movement : yeux à 1,62 m (moins 57 cm accroupi, 84 cm en glissade), balancement de tête
    # au rythme des pas, champ de vision qui s'élargit en sprint (90 -> 98 degrés), tour complet de la caméra pendant la roulade
    cam.data.lens_unit = "FOV"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.clip_start = 0.06
    P["head"].hide_render = True
    P["spine"].hide_render = True          # comme dans un jeu à la première personne : on voit ses bras et ses jambes
    cams = []
    pitch_s, fov_s = -4.0, 90.0
    for k, f in enumerate(F):
        p, lab = f["p"], f["label"]
        lean = p["lean"] * D2R
        ex = f["x"] + 0.5 * math.sin(lean) + 0.06
        ez = f["z"] + 0.62 * math.cos(lean) + 0.05
        if f["ground"]:
            amp = 0.012 + 0.035 * min(1.0, f["v"] / SPRINT)
            ez += amp * (abs(math.sin(f["phi"])) - 0.5)
        tgt = -4.0
        if lab.startswith("Escalade : attraper"):
            tgt = 28.0
        elif lab.startswith("Escalade"):
            tgt = 12.0
        elif lab.startswith("Échelle"):
            tgt = 22.0 if "hisse" not in lab else 5.0
        elif lab.startswith("Chute"):
            tgt = -35.0
        elif lab.startswith("Glissade"):
            tgt = 2.0
        elif lab.startswith("Coup de pied"):
            tgt = -8.0
        elif lab.startswith("Saut"):
            tgt = -8.0
        pitch_s += (tgt - pitch_s) * 0.18
        fov_t = 90.0 + 8.0 * min(1.0, max(0.0, (f["v"] - WALK) / (SPRINT - WALK))) if f["ground"] else fov_s
        fov_s += (fov_t - fov_s) * 0.1
        pitch, roll = pitch_s, (4.0 if lab.startswith("Glissade") and "relève" not in lab else 0.0)
        if f["pivot"] is not None:
            px, pz, ang = f["pivot"]
            a = ang * D2R
            ex, ez = px + 0.35 * math.sin(a), pz + 0.35 * math.cos(a)
            pitch = pitch_s - ang
        cams.append(((ex, 0.0, ez), pitch, roll, fov_s))
    info = []
    for i in frames:
        f = F[i]
        apply_pose(P, f["p"])
        if f["pivot"] is not None:
            px, pz, ang = f["pivot"]
            a = ang * D2R
            off = np.array([0.0, f["z"] - pz])       # bassin au-dessus du pivot
            ox = off[0] * math.cos(a) + off[1] * math.sin(a)
            oz = -off[0] * math.sin(a) + off[1] * math.cos(a)
            P["root"].location = (px + ox, 0, pz + oz)
            P["root"].rotation_euler = (0, a, 0)
        else:
            P["root"].location = (f["x"], 0, f["z"])
            P["root"].rotation_euler = (0, 0, 0)
        # zombie : titube sur place, puis tombe à la renverse après le coup
        zp = dict(ZOMBIE)
        zp["lean"] += 4 * math.sin(i / FPS * 1.7)
        zp["shR"] += 8 * math.sin(i / FPS * 2.3)
        if i >= hitf:
            u = (i - hitf) / FPS
            fall = min(1.0, (u / 0.75) ** 1.6)
            apply_pose(Z, mix(zp, pose(lean=-10, shR=150, shL=130, abdR=40, abdL=40, hipR=20, kneeR=30, head=25), smooth(u / 0.4)))
            Z["root"].location = (zx + 0.9 * smooth(u / 0.9), 0, 0.0)
            Z["root"].rotation_euler = (0, -fall * 88 * D2R, math.pi)
            Z["pelvis"].location = (0, 0, STAND_Z - 0.05 - 0.45 * fall)
        else:
            apply_pose(Z, zp)
            Z["root"].location = (zx, 0, 0.0)
            Z["pelvis"].location = (0, 0, STAND_Z - 0.04)
        c, pitch, roll, fov = cams[i]
        cam.location = c
        cam.rotation_euler = ((90.0 + pitch) * D2R, roll * D2R, -90.0 * D2R)
        cam.data.angle = fov * D2R
        # pendant la roulade, le corps ne doit pas boucher l'objectif
        for k_ in ("shL", "shR", "elbL", "elbR"):
            P[k_].hide_render = f["pivot"] is not None
        out = "video/f_%04d.png" % i
        if not test and os.path.exists(out):          # reprise après interruption
            continue
        bl.render(out)
        info.append(dict(i=i, label=f["label"], key=f["key"], v=f["v"]))
        if i % 25 == 0:
            print("image %d / %d" % (i, len(F)), flush=True)
    json.dump([dict(label=f["label"], key=f["key"], v=f["v"]) for f in F], open("video/legendes.json", "w"), ensure_ascii=False)


def montage():
    """Légendes (mouvement, touche, vitesse) sur chaque image, puis encodage H.264 en MP4."""
    from PIL import Image, ImageDraw, ImageFont
    import imageio_ffmpeg
    leg = json.load(open("video/legendes.json"))
    fonts = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    try:
        fb, fr = ImageFont.truetype(fonts[0], 22), ImageFont.truetype(fonts[1], 16)
    except OSError:
        fb = fr = ImageFont.load_default()
    os.makedirs("video/leg", exist_ok=True)
    n = 0
    for i, l in enumerate(leg):
        src = "video/f_%04d.png" % i
        if not os.path.exists(src):
            break
        im = Image.open(src).convert("RGB")
        d = ImageDraw.Draw(im, "RGBA")
        W, H = im.size
        d.rounded_rectangle([12, 10, 12 + max(200, 22 + int(d.textlength(l["label"], font=fb))), 10 + (62 if l["key"] else 38)], 8,
                            fill=(20, 18, 16, 150))
        d.text((22, 15), l["label"], font=fb, fill=(255, 244, 222))
        if l["key"]:
            d.text((22, 44), l["key"], font=fr, fill=(250, 200, 120))
        if l["label"] not in ("TM Mouvements",):
            t = "%.1f m/s" % l["v"]
            t = t.replace(".", ",")
            tw = d.textlength(t, font=fb)
            d.rounded_rectangle([W - tw - 34, H - 46, W - 12, H - 12], 8, fill=(20, 18, 16, 150))
            d.text((W - tw - 23, H - 42), t, font=fb, fill=(255, 244, 222))
        if l["label"] == "TM Mouvements":
            d.text((22, H - 36), "Plugin TMMouvements — Toits Morts (vue du joueur)", font=fr, fill=(255, 244, 222))
        im.save("video/leg/l_%04d.png" % i)
        n += 1
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([exe, "-y", "-framerate", str(FPS), "-i", "video/leg/l_%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-movflags", "+faststart", "video/mouvements.mp4"], check=True, capture_output=True)
    print("vidéo : %d images -> video/mouvements.mp4" % n)


if __name__ == "__main__":
    if "montage" in sys.argv[1:]:
        montage()
    else:
        main()
