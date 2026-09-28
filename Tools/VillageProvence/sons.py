"""Sons d'ambiance synthétisés (boucles parfaites) : chœur de cigales, filet d'eau de fontaine, souffle du vent,
froissements d'herbes et de feuilles au passage du joueur, grincement et fermeture des portes."""
import numpy as np, wave, sys, os
SR = 32000
OUT = sys.argv[1] if len(sys.argv) > 1 else "sons"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(12)

def band_noise(n, lo, hi):
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= np.exp(-0.5 * ((np.log(np.maximum(f, 1)) - np.log(np.sqrt(lo * hi))) / (0.5 * np.log(hi / lo))) ** 2)
    x = np.fft.irfft(X, n)
    return x / np.abs(x).max()

def save(name, x):
    x = x / np.abs(x).max() * 0.85
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())

# cigales : chaque insecte émet des trains d'impulsions (18 à 30 Hz) sur une bande 4 à 8 kHz, en crescendos
T = 20.0
n = int(T * SR)
t = np.arange(n) / SR
chorus = np.zeros(n)
for k in range(14):
    carrier = band_noise(n, rng.uniform(3800, 5200), rng.uniform(6500, 9000))
    rate = round(rng.uniform(18, 30) * T) / T
    duty = rng.uniform(0.3, 0.5)
    ph = (t * rate + rng.random()) % 1.0
    pulses = np.clip(1 - np.abs(ph - duty / 2) / (duty / 2), 0, 1) ** 0.6
    # enveloppe lente périodique (crescendo / silence), raccord parfait
    cyc = rng.integers(1, 4)
    env = 0.5 - 0.5 * np.cos(2 * np.pi * (t * cyc / T + rng.random()))
    env = np.clip(env * 1.4 - 0.2, 0, 1) ** 1.5
    chorus += carrier * pulses * env * rng.uniform(0.5, 1.0)
save("Cigales.wav", chorus)

# fontaine : bruit rose doux + gouttes (sinus amortis) réparties sur la boucle
T = 12.0
n = int(T * SR)
water = band_noise(n, 300, 5000) * 0.35 + band_noise(n, 1500, 9000) * 0.2
for i in range(int(T * 28)):
    t0 = rng.integers(0, n)
    f0 = rng.uniform(900, 3200)
    L = int(SR * rng.uniform(0.01, 0.05))
    tt = np.arange(L) / SR
    drop = np.sin(2 * np.pi * (f0 + 2500 * tt) * tt) * np.exp(-tt * rng.uniform(60, 160)) * rng.uniform(0.2, 0.8)
    idx = (t0 + np.arange(L)) % n
    water[idx] += drop
save("Fontaine.wav", water)
# rivière au fond des gorges : grondement grave et large, clapotis et éclaboussures (boucle parfaite)
T = 16.0
n = int(T * SR)
t = np.arange(n) / SR
river = band_noise(n, 80, 900) * 0.8 + band_noise(n, 400, 3000) * 0.45 + band_noise(n, 2000, 8000) * 0.12
river *= 1.0 + 0.25 * np.sin(2 * np.pi * t * 3 / T) + 0.12 * np.sin(2 * np.pi * t * 7 / T + 1.3)
for i in range(int(T * 40)):
    t0 = rng.integers(0, n)
    L = int(SR * rng.uniform(0.02, 0.09))
    tt = np.arange(L) / SR
    spl = band_noise(L, 600, 4000)[:L] * np.exp(-tt * rng.uniform(25, 70)) * rng.uniform(0.1, 0.35)
    idx = (t0 + np.arange(L)) % n
    river[idx] += spl
save("Riviere.wav", river)
# vent : souffle grave qui enfle et retombe, sifflement léger dans les rafales (boucle parfaite : tout est périodique sur T)
T = 24.0
n = int(T * SR)
t = np.arange(n) / SR
low = band_noise(n, 60, 700)
mid = band_noise(n, 400, 2500)
env = np.zeros(n)
for k, a in ((1, 0.5), (2, 0.35), (3, 0.25), (5, 0.15)):
    env += a * np.cos(2 * np.pi * (k * t / T + rng.random()))
env = np.clip(0.55 + 0.5 * env / 1.25, 0.12, 1.0)
whistle = np.zeros(n)
for f0 in (520, 690, 880):
    whistle += band_noise(n, f0 * 0.97, f0 * 1.03)
wind = low * env + 0.35 * mid * env ** 2 + 0.08 * whistle * np.clip(env - 0.6, 0, 1) * 2.5
save("Vent.wav", wind)

# froissements : craquements secs (tiges, feuilles) sur un souffle de frottement, 4 variantes courtes
for v in range(4):
    L = rng.uniform(0.38, 0.55)
    n = int(L * SR)
    t = np.arange(n) / SR
    body = band_noise(n, 900, 6000) * np.sin(np.pi * t / L) ** 1.5 * 0.5
    crack = np.zeros(n)
    dens = np.sin(np.pi * t / L) ** 0.8
    for i in range(int(rng.uniform(60, 110))):
        c = int(rng.choice(n, p=dens / dens.sum()))
        m = int(SR * rng.uniform(0.002, 0.008))
        b = rng.standard_normal(m) * np.exp(-np.arange(m) / (m * 0.3)) * rng.uniform(0.2, 1.0)
        crack[c:c + m] += b[:max(0, min(m, n - c))]
    X = np.fft.rfft(crack)
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= np.clip((f - 1500) / 1500, 0, 1)
    crack = np.fft.irfft(X, n)
    x = body + crack / (np.abs(crack).max() + 1e-9) * 0.8
    fade = np.minimum(1, np.minimum(t / 0.015, (L - t) / 0.06))
    save(f"Froissement_{v}.wav", x * fade)
# porte : grincement de gonds (frottement saccadé filtré par des résonances du bois) puis claquement sourd + loquet
def resonate(x, freqs, q=30.0):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = sum(1.0 / (1.0 + (q * (f / f0 - f0 / np.maximum(f, 1))) ** 2) for f0 in freqs)
    return np.fft.irfft(X * H, len(x))

L = 1.3
n = int(L * SR)
t = np.arange(n) / SR
rate = 45 + 35 * np.sin(np.pi * t / L) + 8 * np.sin(2 * np.pi * 3.1 * t)
ph = np.cumsum(rate) / SR
pulses = (np.diff(np.floor(ph), prepend=0) > 0).astype(float) * rng.uniform(0.5, 1.0, n)
creak = resonate(pulses + 0.02 * rng.standard_normal(n), [520, 1180, 2300], q=25)
env = np.sin(np.pi * np.clip(t / L, 0, 1)) ** 0.6
save("Porte_Ouverture.wav", creak * env)
L = 0.7
n = int(L * SR)
t = np.arange(n) / SR
thump = np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.08) + 0.6 * band_noise(n, 80, 600) * np.exp(-t / 0.05)
click = np.zeros(n)
c0 = int(0.035 * SR)
click[c0:c0 + 400] = rng.standard_normal(400) * np.exp(-np.arange(400) / 60)
click = resonate(click, [2600, 4100], q=12)
save("Porte_Fermeture.wav", thump + 0.5 * click / (np.abs(click).max() + 1e-9))
print("ok")
