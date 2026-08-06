"""FDD must not hand back noise dressed as modes.

`test_2dof.csv` has known modes at 10 and 25 Hz. With no prominence filter the
picker returned the ten most prominent local maxima of the SV1 curve — the two
real modes plus eight pieces of noise, each with a damping ratio and a mode
shape attached, indistinguishable in the table.

Run via `python tests/run_all.py`, or standalone against a running backend:

    python tests/api/test_fdd_defaults.py http://127.0.0.1:8000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from http_util import Results, post  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "test_2dof.csv"

TRUE_MODES = (10.0, 25.0)


def make_session(base):
    st, sess = post(base, "/api/session/create", {}, {"file": (CSV.name, CSV.read_bytes())})
    if st != 200:
        raise SystemExit(f"cannot create session: {st}")
    return sess


def run_fdd(base, sess, cols, **extra):
    fields = dict(
        session_id=sess["session_id"],
        orientation=sess["orientation"],
        header_row=sess["header_row"],
        time_col=sess["time_col"],
        fs=sess["fs"],
        signal_cols=str(list(cols)).replace(" ", ""),
        window="hann",
        nperseg=1024,
        mac_threshold=0.8,
        n_crossings=10,
    )
    fields.update(extra)
    return post(base, "/api/fdd/analyze", fields)


def test_defaults_find_only_the_real_modes(base, sess, r):
    r.section("defaults on the two response channels")
    st, d = run_fdd(base, sess, [1, 2])
    if not r.check(st == 200, "fdd runs", str(st)):
        return
    peaks = [round(f, 1) for f in d["peak_freqs"]]
    r.check(peaks == list(TRUE_MODES),
            "exactly the two true modes, and nothing else", str(peaks))
    r.check(d["criteria"]["n_candidates"] > 50,
            "there were plenty of local maxima to reject",
            str(d["criteria"]["n_candidates"]))
    r.check(d["criteria"]["n_accepted"] == 2, "two survived",
            str(d["criteria"]["n_accepted"]))
    r.check(d["criteria"]["defaulted"] is True,
            "and the response says these were defaults")
    r.check(all(x >= 6 for x in d["peak_dominance_db"]),
            "every reported peak clears the dominance gate",
            str([round(x, 1) for x in d["peak_dominance_db"]]))
    r.check(len(d["damping_ratios"]) == 2,
            "damping is reported for exactly the accepted peaks")


def test_peaks_are_in_frequency_order(base, sess, r):
    r.section("mode ordering")
    st, d = run_fdd(base, sess, [1, 2], min_dominance_db=0, prominence=0.5, max_peaks=8)
    if not r.check(st == 200, "fdd runs with a loose filter", str(st)):
        return
    freqs = list(d["peak_freqs"])
    # dspkit ranks by prominence, which is right for truncation and wrong for a
    # table someone reads top to bottom as a mode list.
    r.check(freqs == sorted(freqs), "modes come back in frequency order",
            str([round(f, 1) for f in freqs[:5]]))


def test_force_channels_yield_nothing(base, sess, r):
    r.section("the documented trap: force channels included")
    st, d = run_fdd(base, sess, [1, 2, 3, 4])
    if not r.check(st == 200, "fdd still runs", str(st)):
        return
    # This selection is meaningless for an output-only method. Returning nothing
    # is the correct answer; it used to return 285/442/72 Hz with damping.
    r.check(d["peak_freqs"] == [],
            "no modes are invented from excitation channels",
            str([round(f, 1) for f in d["peak_freqs"]]))
    r.check(d["damping_ratios"] == [],
            "and no damping ratios are attached to nothing")
    r.check(d["criteria"]["n_accepted"] == 0, "reported as zero accepted")
    r.check(d["criteria"]["n_candidates"] > 0,
            "while still saying how many candidates were considered",
            str(d["criteria"]["n_candidates"]))


def test_old_behaviour_is_still_reachable(base, sess, r):
    r.section("the thresholds are not a cage")
    st, d = run_fdd(base, sess, [1, 2], prominence=0.5, min_dominance_db=0, max_peaks=10)
    if not r.check(st == 200, "explicit settings run", str(st)):
        return
    r.check(len(d["peak_freqs"]) == 10,
            "lowering both thresholds brings the noise peaks back",
            str(len(d["peak_freqs"])))
    r.check(d["criteria"]["defaulted"] is False,
            "and the response no longer claims defaults")
    r.check(d["criteria"]["prominence_db"] == 0.5,
            "the criteria echo what was actually applied")


def test_explicit_prominence_keeps_dominance_gate(base, sess, r):
    r.section("the two gates are independent")
    # A user lowering prominence has not asked to disable the dominance check.
    st, d = run_fdd(base, sess, [1, 2], prominence=0.5)
    if not r.check(st == 200, "runs", str(st)):
        return
    r.check(len(d["peak_freqs"]) == 2,
            "dominance alone still rejects the noise", str(len(d["peak_freqs"])))
    r.check(d["criteria"]["min_dominance_db"] == 6.0,
            "the dominance default is unchanged by a prominence override")


def test_dominance_alone_is_enough(base, sess, r):
    r.section("dominance without prominence")
    st, d = run_fdd(base, sess, [1, 2], prominence=0, min_dominance_db=6)
    if not r.check(st == 200, "runs", str(st)):
        return
    peaks = [round(f, 1) for f in d["peak_freqs"]]
    r.check(peaks == list(TRUE_MODES),
            "SV1/SV2 separation alone recovers the true modes", str(peaks))


def main(base):
    r = Results()
    print(f"FDD default tests against {base}")
    sess = make_session(base)
    test_defaults_find_only_the_real_modes(base, sess, r)
    test_peaks_are_in_frequency_order(base, sess, r)
    test_force_channels_yield_nothing(base, sess, r)
    test_old_behaviour_is_still_reachable(base, sess, r)
    test_explicit_prominence_keeps_dominance_gate(base, sess, r)
    test_dominance_alone_is_enough(base, sess, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
