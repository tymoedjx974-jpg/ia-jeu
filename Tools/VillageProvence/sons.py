"""Sons d'ambiance synthétisés (boucles parfaites) : chœur de cigales, filet d'eau de fontaine."""
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
print("ok")
