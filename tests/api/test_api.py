"""API behaviour against a live backend, driven with the real example file.

Run via `python tests/run_all.py`, which starts the server. To run standalone
against an already-running backend:

    python tests/api/test_api.py http://127.0.0.1:8000
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from http_util import Results, post  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "test_2dof.csv"


def make_session(base, r):
    raw = CSV.read_bytes()
    st, sess = post(base, "/api/session/create", {}, {"file": (CSV.name, raw)})
    r.check(st == 200, "session/create returns 200", str(st))
    if st != 200:
        raise SystemExit("cannot continue without a session")

    names = sess["column_names"]
    r.check(names == ["time", "x1_disp", "x2_disp", "force1", "force2"],
            "column names are read from the header", str(names))
    r.check(sess["time_col"] == 0, "time column is auto-detected", str(sess["time_col"]))
    r.check(abs(sess["fs"] - 1024) < 1, "fs is derived from the time column",
            f"{sess['fs']:.2f} Hz")
    r.check(sess["n_samples"] == 20480, "sample count", str(sess["n_samples"]))
    return sess


def base_fields(sess, cols):
    return dict(
        session_id=sess["session_id"],
        orientation=sess["orientation"],
        header_row=sess["header_row"],
        time_col=sess["time_col"],
        fs=sess["fs"],
        signal_cols=json.dumps(cols),
    )


def test_overview(base, sess, r):
    """The three calls the Overview tab composes on load."""
    r.section("Overview composes three endpoints")
    f = base_fields(sess, [1, 2, 3, 4])

    st, ts = post(base, "/api/signal/timeseries", f)
    r.check(st == 200 and len(ts.get("signals", [])) == 4,
            "timeseries returns every selected channel")

    st, psd = post(base, "/api/spectral/psd",
                   {**f, "window": "hann", "nperseg": 1024, "scaling": "density"})
    r.check(st == 200 and len(psd.get("signals", [])) == 4,
            "psd returns every selected channel")

    st, fdd = post(base, "/api/fdd/analyze", {**f, "window": "hann", "nperseg": 1024,
                                              "mac_threshold": 0.8, "n_crossings": 10})
    r.check(st == 200 and fdd["labels"] == ["x1_disp", "x2_disp", "force1", "force2"],
            "fdd reports the channels it used, so the caveat can name them")


def test_fdd_needs_response_channels(base, sess, r):
    """Regression: FDD is output-only, and including the force columns wrecks it.

    This is why the Overview panel names its channels and states the assumption.
    """
    r.section("FDD is output-only (the reason the UI says so)")

    st, good = post(base, "/api/fdd/analyze",
                    {**base_fields(sess, [1, 2]), "window": "hann", "nperseg": 1024})
    top2 = sorted(round(x) for x in good["peak_freqs"][:2]) if st == 200 else []
    r.check(top2 == [10, 25],
            "responses only: top two peaks are the true 10 and 25 Hz modes", str(top2))

    st, bad = post(base, "/api/fdd/analyze",
                   {**base_fields(sess, [1, 2, 3, 4]), "window": "hann", "nperseg": 1024})
    bad2 = sorted(round(x) for x in bad["peak_freqs"][:2]) if st == 200 else []
    r.check(bad2 != [10, 25],
            "with force channels included the modes are lost -- the documented trap",
            str(bad2))


def test_fanout(base, sess, r):
    """'All selected' issues one request per channel, all naming signal_col."""
    r.section("Single-channel fan-out")
    f = base_fields(sess, [1, 2, 3, 4])
    for col, name in [(1, "x1_disp"), (2, "x2_disp"), (3, "force1"), (4, "force2")]:
        st, d = post(base, "/api/timefreq/stft",
                     {**f, "signal_col": col, "window": "hann", "nperseg": 256})
        r.check(st == 200 and len(d["freqs"]) > 0 and len(d["times"]) > 0,
                f"stft on {name}", f"{len(d.get('freqs', []))}x{len(d.get('times', []))}")


def test_single_channel(base, sess, r):
    """One selected channel must not block exploration."""
    r.section("A single selected channel reaches everything but the matrices")
    one = 1
    f = base_fields(sess, [one])

    works = [
        ("timeseries",       "/api/signal/timeseries", {}),
        ("fft",              "/api/spectral/fft", {"window": "hann", "scaling": "amplitude"}),
        ("psd",              "/api/spectral/psd",
                             {"window": "hann", "nperseg": 1024, "scaling": "density"}),
        ("autocorrelation",  "/api/spectral/autocorrelation", {"normalize": True}),
        ("peaks",            "/api/peaks/detect",
                             {"signal_col": one, "spectrum_type": "fft", "window": "hann",
                              "scaling": "amplitude", "max_peaks": 3}),
        ("indicators",       "/api/indicators", {"signal_col": one, "segment_duration": 1.0}),
        ("filter",           "/api/filter/apply",
                             {"signal_col": one, "filter_type": "lowpass", "cutoff": 100,
                              "order": 4, "zero_phase": True}),
        ("stft",             "/api/timefreq/stft",
                             {"signal_col": one, "window": "hann", "nperseg": 256}),
        ("instantaneous",    "/api/instantaneous", {"signal_col": one}),
        ("cross-corr X=Y",   "/api/spectral/cross_correlation",
                             {"signal_col_x": one, "signal_col_y": one, "normalize": True}),
        ("csd X=Y",          "/api/spectral/csd",
                             {"signal_col_x": one, "signal_col_y": one,
                              "window": "hann", "nperseg": 1024}),
        ("coherence X=Y",    "/api/spectral/coherence",
                             {"signal_col_x": one, "signal_col_y": one,
                              "window": "hann", "nperseg": 1024}),
        ("stats pdf",        "/api/statistics/pdf", {"signal_col": one, "bins": 50}),
        ("stats joint X=Y",  "/api/statistics/joint",
                             {"signal_col_x": one, "signal_col_y": one, "bins": 50}),
    ]
    for label, url, extra in works:
        st, d = post(base, url, {**f, **extra})
        r.check(st == 200, f"reachable with one channel: {label}",
                "" if st == 200 else str(d)[:70])

    r.section("Genuinely between-sensor analyses refuse, with a reason")
    for label, url, extra in [
        ("fdd",         "/api/fdd/analyze", {"window": "hann", "nperseg": 1024}),
        ("multisensor", "/api/multisensor/correlation", {}),
        ("covariance",  "/api/statistics/covariance", {}),
        ("mahalanobis", "/api/statistics/mahalanobis", {"percentile": 99}),
    ]:
        st, d = post(base, url, {**f, **extra})
        r.check(st == 422 and "2 channels" in str(d), f"{label} refuses one channel",
                f"{st} {str(d.get('detail', d))[:45]}")

    # The UI tells the user this; make sure it stays true.
    st, d = post(base, "/api/spectral/coherence",
                 {**f, "signal_col_x": one, "signal_col_y": one,
                  "window": "hann", "nperseg": 1024})
    if st == 200:
        lo, hi = min(d["Cxy"]), max(d["Cxy"])
        r.check(lo > 0.999 and hi <= 1.0001,
                "coherence(x, x) == 1, as the single-channel hint claims",
                f"[{lo:.6f}, {hi:.6f}]")


def test_session_errors(base, sess, r):
    r.section("Session handling")
    st, d = post(base, "/api/signal/timeseries",
                 {**base_fields(sess, [1]), "session_id": "does-not-exist"})
    r.check(st == 404, "an unknown session is 404, not 500", str(st))
    r.check("reload" in str(d).lower(), "and says what to do about it",
            str(d.get("detail", ""))[:60])

    st, d = post(base, "/api/spectral/fft",
                 {**base_fields(sess, []), "window": "hann", "scaling": "amplitude"})
    r.check(st == 422, "an empty channel selection is rejected", str(st))


def main(base):
    r = Results()
    print(f"API tests against {base}")
    sess = make_session(base, r)
    test_overview(base, sess, r)
    test_fdd_needs_response_channels(base, sess, r)
    test_fanout(base, sess, r)
    test_single_channel(base, sess, r)
    test_session_errors(base, sess, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
