"""
Generate a 2-DOF system response under white noise excitation.

System:
    m1*x1'' + (c1+c2)*x1' - c2*x2' + (k1+k2)*x1 - k2*x2 = F1(t)
    m2*x2'' - c2*x1' + c2*x2' - k2*x1 + k2*x2 = F2(t)

Parameters chosen so that:
    f1 ≈ 10 Hz  (first natural frequency)
    f2 ≈ 25 Hz  (second natural frequency)
    ζ1 = ζ2 ≈ 2% (Rayleigh damping)

Output CSV columns: time, x1, x2, force1, force2
"""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eig

# ── System parameters ─────────────────────────────────────────────────────────
m1 = m2 = 1.0        # kg

k1 = 17_500.0        # N/m  (spring to ground)
k2 =  5_575.0        # N/m  (inter-mass spring)

# Rayleigh damping C = α*M + β*K  →  ζ ≈ 2% at both natural frequencies
alpha = 1.795
beta  = 1.819e-4

M = np.array([[m1,  0 ],
              [ 0, m2 ]])
K = np.array([[k1+k2, -k2],
              [-k2,    k2]])
C = alpha * M + beta * K

Minv = np.linalg.inv(M)

# ── State-space matrices ──────────────────────────────────────────────────────
# State: y = [x1, x2, x1', x2']
A = np.zeros((4, 4))
A[:2, 2:] = np.eye(2)
A[2:, :2] = -Minv @ K
A[2:, 2:] = -Minv @ C

B = np.zeros((4, 2))
B[2:] = Minv          # force input to accelerations

# ── Print natural frequencies ─────────────────────────────────────────────────
eigvals, _ = eig(K, M)
omega_n = np.sqrt(eigvals.real)
f_n = np.sort(omega_n / (2 * np.pi))
print(f"Natural frequencies:  f1 = {f_n[0]:.2f} Hz,  f2 = {f_n[1]:.2f} Hz")

# ── Simulation settings ───────────────────────────────────────────────────────
fs  = 1024    # Hz  (power of 2 — convenient for FFT)
dt  = 1 / fs
T   = 20.0   # s
N   = int(T * fs)
t   = np.arange(N) * dt

# ── White noise excitation ────────────────────────────────────────────────────
rng = np.random.default_rng(42)
F   = rng.standard_normal((N, 2)) * 50.0   # N, applied to both DOFs

# ── Integrate (RK4 fixed-step via solve_ivp dense=False for speed) ────────────
# Pre-interpolate forces onto a callable for solve_ivp
def ode(t_val, y):
    idx = min(int(t_val * fs), N - 1)
    return A @ y + B @ F[idx]

print("Integrating (this may take a few seconds)…")
sol = solve_ivp(
    ode,
    t_span=(0, T),
    y0=np.zeros(4),
    method="RK45",
    t_eval=t,
    rtol=1e-6,
    atol=1e-9,
)

x1 = sol.y[0]
x2 = sol.y[1]

# ── Save CSV ──────────────────────────────────────────────────────────────────
import csv, pathlib

out = pathlib.Path(__file__).parent / "test_2dof.csv"
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["time", "x1_disp", "x2_disp", "force1", "force2"])
    for i in range(N):
        w.writerow([
            round(t[i], 6),
            round(x1[i], 9),
            round(x2[i], 9),
            round(F[i, 0], 6),
            round(F[i, 1], 6),
        ])

print(f"Saved {N} samples → {out}")
print(f"  fs = {fs} Hz,  duration = {T:.0f} s")
print(f"  Columns: time, x1_disp, x2_disp, force1, force2")
print(f"  Use column 0 as time, columns 1 or 2 as signal.")
print(f"  Try PSD with nperseg=4096 — you should see peaks at ~10 Hz and ~25 Hz.")
