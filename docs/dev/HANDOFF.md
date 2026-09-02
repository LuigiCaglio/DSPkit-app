# DSPkit — handoff

State as of **2026-09-02**. Covers both repos:

| | path | branch | remote | visibility |
|---|---|---|---|---|
| library | `../DSPkit` | `main` | `LuigiCaglio/DSPkit` | **public**, MIT |
| app | `.` | `master` | `LuigiCaglio/DSPkit-app` | **private**, no licence |

Living task lists stay where they are — this file does not duplicate them:
- `TODO.md` (here) — app work.
- `../DSPkit/TODO.md` — library work: response spectrum, tapering the
  autocorrelation, the FSST inverse.

---

## 1. Where things stand

Both repos are **clean and fully pushed** (0 ahead, 0 behind their remotes).
Last commit on each: 2026-08-07 16:24.

Tests, both green, re-run 2026-09-02:
- library — `pytest tests/` in `../DSPkit`: **189 passed**
- app — `python tests/run_all.py`: **all suites passed**, 171 frontend
  assertions plus the API, persistence, detection and FDD suites

The stale `plug-and-play-gui` branch is **fully merged** into `master`
(0 commits unique to it, master is 10 ahead). It exists locally and on the
remote and can be deleted:

```
git branch -d plug-and-play-gui && git push origin --delete plug-and-play-gui
```

---

## 2. Open decision A — making the app public

The library is already public. The app is not, and is **not ready to be**.
Nothing here is hard; it is a checklist, not a project.

**Blocking**

1. ~~Author email in commit metadata.~~ **Done 2026-09-02** — see §4.
2. **No `LICENSE`.** Without one the default is "all rights reserved", which
   contradicts publishing. The library is MIT; matching it is the obvious call.
3. **No `README`.** The repo root currently opens on `GUI_BUILD_INSTRUCTIONS.md`
   and `GUI_TEMPLATE_FOR_CLAUDE.md`, which are internal working notes.
4. **The example dataset is not in the repo.** `.gitignore` excludes `*.csv`, so
   `example_data/2dof_vibration.csv` is untracked. On a fresh clone
   `/api/example-data` finds nothing, the "load an example" button never
   appears, and a new user has no data to try. Either force-add it
   (`git add -f`, 1.1 MB) or have `run.py` generate it via the tracked
   `generate_test_signal.py` on first start.

**Worth doing before strangers arrive** — all already in `TODO.md`:

- §1.3 error messages are raw `f"{type(e).__name__}: {e}"` strings.
- §1.1 CSV/TSV/TXT only. Deliberately closed for your own use; reopens the
  moment someone else's `.mat` or `.tdms` shows up.
- §4 bundle is 4.9 MB (1.5 MB gzipped), nearly all Plotly. Fine on localhost,
  not fine if anyone ever serves it remotely.

**Checked and clean:** no personal paths, absolute paths, or credentials in any
tracked file in either repo.

---

## 3. Open decision B — coherence, multi-coherence, mutual information

The goal: given a set of signals, decide whether they carry enough information
to predict the rest. Notes toward that, not a plan yet.

**What already exists**

- `dspkit.multisensor.coherence_matrix` — pairwise magnitude-squared coherence,
  `(n_ch, n_ch, M)`. Ordinary coherence only.
- `dspkit.multisensor.psd_matrix` — the **full complex CSD matrix**
  `G[i, j, f]`, Hermitian, written for FDD.
- App: `/api/spectral/coherence` (a pair) and `/api/multisensor/coherence_matrix`.

**Why `psd_matrix` matters.** Multiple and partial coherence are both functions
of the *inverse* of that matrix, which already exists and is already tested:

- multiple coherence of channel *i* against all others:
  `1 − 1 / (G_ii · (G⁻¹)_ii)`
- partial coherence between *i* and *j*, conditioning out the rest:
  `|(G⁻¹)_ij|² / ((G⁻¹)_ii · (G⁻¹)_jj)`

So the linear half of the question is a small addition to `multisensor.py`
rather than new machinery. The care needed is in conditioning, not in the
formula: `G` is near-singular wherever channels are nearly redundant — which is
exactly the case being tested for — so it wants pseudo-inverse or ridge
regularisation, and enough Welch averages that `G` is full rank at all
(`n_segments > n_channels`, or every coherence reads 1.0 and means nothing).

**Mutual information is a different animal.** It catches nonlinear and
lag-dependent dependence that coherence cannot, but it is an estimation problem,
not a transform: binned estimators are badly biased at realistic sample sizes,
so it wants a k-NN (Kraskov–Stögbauer–Grassberger) estimator, and it needs a
stated answer on lags and on how to report significance.

**Open question before any code:** "enough info to predict the rest" is a
modelling claim, and coherence is a *per-frequency* one. Deciding what the app
should actually assert — and at what frequency, over what band, with what
null — is the design work. It is worth settling that before picking estimators.

---

## 4. Email in commit metadata — done 2026-09-02

A personal address was the author **and** committer email on every commit
in both repos. It is now gone from both, local and remote:

| repo | commits | before | after |
|---|---|---|---|
| DSPkit | 15 | the personal address | noreply only |
| DSPkit-app | 34 | the personal address | noreply only |

No email ever appeared in a tracked file or a commit message. The only address
in message bodies is `noreply@anthropic.com`, from `Co-Authored-By` trailers,
which is Anthropic's and stays.

What was done:

- Global git config set to `83336089+LuigiCaglio@users.noreply.github.com`, so
  new commits cannot regress. Neither repo overrides it.
- On GitHub: *Keep my email addresses private* and *Block command line pushes
  that expose my email* both enabled — the second makes a regression impossible
  rather than merely unlikely.
- `DSPkit` history was rewritten and force-pushed, then the local clone was
  reset to match (trees verified identical first).
- `DSPkit-app` history was rewritten with `git filter-repo --mailmap` and
  force-pushed. Verified before pushing: same 34 commits, same tree hash
  `94053e2…`, same subjects in the same order — only metadata changed.
- The stale `plug-and-play-gui` branch was deleted locally and on the remote
  (fully merged, 0 unique commits).

**The one caveat.** GitHub keeps rewritten commits reachable by direct SHA for
a period, and its public event archives retain the old metadata regardless.
This closes off future exposure; it does not undo the past. For `DSPkit-app`
that hardly matters — it was never public. For `DSPkit`, which has been public
since its first commit, assume the address was already harvested and treat this
as stopping the bleed rather than as a clean slate.

A mirror backup of the pre-rewrite `DSPkit-app` sits in this session's
scratchpad (`DSPkit-app-backup.git`, 34 commits at `9ef0dc2`). It is temporary
— delete it once GitHub looks right, or copy it somewhere durable if you want
to keep it.
