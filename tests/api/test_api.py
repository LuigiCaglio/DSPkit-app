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


def test_preprocessing_reaches_analyses(base, sess, r):
    """A cutoff picked on the spectrum must actually change the spectrum.

    The UI sets hp_cutoff/lp_cutoff as query parameters (buildPreprocUrl) and
    then replays the last request. If that plumbing breaks, the red band still
    renders and the numbers still update, but nothing is filtered -- which looks
    exactly like it is working.
    """
    r.section("Preprocessing cutoffs reach the analyses")
    f = base_fields(sess, [1])
    band = 50.0

    st, plain = post(base, "/api/spectral/fft",
                     {**f, "window": "hann", "scaling": "amplitude"})
    st_hp, hp = post(base, f"/api/spectral/fft?hp_cutoff={band}",
                     {**f, "window": "hann", "scaling": "amplitude"})
    if not r.check(st == 200 and st_hp == 200, "fft responds with and without a high-pass"):
        return

    def energy_below(d, cutoff):
        return sum(a for fq, a in zip(d["freqs"], d["signals"][0]["amplitude"]) if fq < cutoff)

    def energy_above(d, cutoff):
        return sum(a for fq, a in zip(d["freqs"], d["signals"][0]["amplitude"]) if fq > cutoff)

    lo_plain, lo_hp = energy_below(plain, band), energy_below(hp, band)
    r.check(lo_hp < lo_plain * 0.2,
            "a high-pass removes most of the content below its cutoff",
            f"{lo_plain:.4g} -> {lo_hp:.4g}")

    hi_plain, hi_hp = energy_above(plain, band * 2), energy_above(hp, band * 2)
    r.check(abs(hi_hp - hi_plain) < hi_plain * 0.1 + 1e-12,
            "and leaves the pass band alone", f"{hi_plain:.4g} -> {hi_hp:.4g}")

    # Low-pass, the mirror case.
    st_lp, lp = post(base, f"/api/spectral/fft?lp_cutoff={band}",
                     {**f, "window": "hann", "scaling": "amplitude"})
    hi_lp = energy_above(lp, band)
    r.check(st_lp == 200 and hi_lp < energy_above(plain, band) * 0.2,
            "a low-pass removes most of the content above its cutoff",
            f"{energy_above(plain, band):.4g} -> {hi_lp:.4g}")

    # Band-pass is the two together, which is how the UI represents it.
    st_bp, bp = post(base, "/api/spectral/fft?hp_cutoff=20&lp_cutoff=200",
                     {**f, "window": "hann", "scaling": "amplitude"})
    r.check(st_bp == 200
            and energy_below(bp, 20) < energy_below(plain, 20) * 0.2
            and energy_above(bp, 200) < energy_above(plain, 200) * 0.2,
            "a band-pass is the high-pass and low-pass together")

    # The same plumbing carries the PSD, which is where the band is picked.
    st_psd, psd_hp = post(base, f"/api/spectral/psd?hp_cutoff={band}",
                          {**f, "window": "hann", "nperseg": 1024, "scaling": "density"})
    st_psd0, psd0 = post(base, "/api/spectral/psd",
                         {**f, "window": "hann", "nperseg": 1024, "scaling": "density"})
    if st_psd == 200 and st_psd0 == 200:
        below = lambda d: sum(  # noqa: E731
            p for fq, p in zip(d["freqs"], d["signals"][0]["Pxx"]) if fq < band)
        r.check(below(psd_hp) < below(psd0) * 0.2,
                "the PSD is filtered the same way", f"{below(psd0):.4g} -> {below(psd_hp):.4g}")


def test_filter_options(base, sess, r):
    """Detrend, notch, order and zero-phase are exposed, and each does its job."""
    r.section("Preprocessing filter options")
    f = base_fields(sess, [1])
    fft = lambda q: post(  # noqa: E731
        base, f"/api/spectral/fft{q}", {**f, "window": "hann", "scaling": "amplitude"})

    # Detrend, measured on the signal itself rather than through a windowed FFT:
    # order 0 must drive the mean to zero, order 1 must also flatten the slope.
    fg = base_fields(sess, [3])          # force1 has a non-zero mean
    st0, plain = post(base, "/api/signal/timeseries", fg)
    st1, dt0 = post(base, "/api/signal/timeseries?detrend_order=0", fg)
    if r.check(st0 == 200 and st1 == 200, "timeseries responds with and without detrend"):
        mean = lambda d: sum(d["signals"][0]["signal_proc"]) / len(d["signals"][0]["signal_proc"])  # noqa: E731
        m0, m1 = mean(plain), mean(dt0)
        r.check(abs(m1) < abs(m0) * 1e-6 + 1e-9,
                "detrend order 0 removes the mean", f"{m0:.6g} -> {m1:.3g}")

    st2, dt1 = post(base, "/api/signal/timeseries?detrend_order=1", fg)
    if r.check(st2 == 200, "linear detrend is accepted"):
        y = dt1["signals"][0]["signal_proc"]
        n = len(y)
        # Least-squares slope; a linear detrend must leave essentially none.
        xs = list(range(n))
        xbar, ybar = (n - 1) / 2, sum(y) / n
        num = sum((xi - xbar) * (yi - ybar) for xi, yi in zip(xs, y))
        den = sum((xi - xbar) ** 2 for xi in xs)
        slope = num / den if den else 0.0
        spread = max(y) - min(y)
        r.check(abs(slope) * n < spread * 1e-6,
                "detrend order 1 removes the linear trend",
                f"slope*n = {abs(slope) * n:.3g} vs range {spread:.3g}")

    # Order: a higher order rolls off faster, so less survives beyond the cutoff.
    st_a, o2 = fft("?lp_cutoff=50&lp_order=2")
    st_b, o8 = fft("?lp_cutoff=50&lp_order=8")
    if r.check(st_a == 200 and st_b == 200, "order is accepted"):
        beyond = lambda d: sum(  # noqa: E731
            a for fq, a in zip(d["freqs"], d["signals"][0]["amplitude"]) if fq > 75)
        r.check(beyond(o8) < beyond(o2),
                "a higher order rolls off faster", f"{beyond(o2):.4g} -> {beyond(o8):.4g}")

    # Zero-phase off is a different (causal) result.
    st_c, causal = fft("?lp_cutoff=50&zero_phase=false")
    st_d, zp = fft("?lp_cutoff=50&zero_phase=true")
    if r.check(st_c == 200 and st_d == 200, "zero_phase is accepted both ways"):
        r.check(causal["signals"][0]["amplitude"] != zp["signals"][0]["amplitude"],
                "causal and zero-phase give different results")

    # Notch: energy at the notch frequency drops, neighbours survive.
    st_n0, no_notch = fft("")
    st_n1, notched = fft("?notch_freq=10&notch_q=30")
    if r.check(st_n0 == 200 and st_n1 == 200, "notch is accepted"):
        at = lambda d, f0, w: sum(  # noqa: E731
            a for fq, a in zip(d["freqs"], d["signals"][0]["amplitude"]) if abs(fq - f0) < w)
        r.check(at(notched, 10, 0.5) < at(no_notch, 10, 0.5),
                "a notch attenuates its own frequency",
                f"{at(no_notch, 10, 0.5):.4g} -> {at(notched, 10, 0.5):.4g}")
        far0, far1 = at(no_notch, 200, 5), at(notched, 200, 5)
        r.check(abs(far1 - far0) < far0 * 0.05 + 1e-12,
                "and leaves distant frequencies alone", f"{far0:.4g} -> {far1:.4g}")


def test_filter_response(base, sess, r):
    """The response curve drawn over the spectrum must be the filter that runs."""
    r.section("Filter response endpoint")
    fs = 1024.0

    st, d = post(base, "/api/filter/response",
                 {"fs": fs, "lp_cutoff": 100, "lp_order": 4, "zero_phase": "false"})
    if not r.check(st == 200 and d.get("applied"), "response returns a curve", str(st)):
        return
    r.check(len(d["freqs"]) == len(d["magnitude"]), "freqs and magnitude line up")
    r.check(d["freqs"][-1] <= fs / 2 + 1e-9, "the curve stops at Nyquist", f"{d['freqs'][-1]:.1f}")
    r.check(max(d["magnitude"]) <= 1.0001, "gain never exceeds 1", f"{max(d['magnitude']):.4f}")

    # A single-pass Butterworth is exactly -3 dB at its cutoff.
    r.check(d["minus3db"] and abs(d["minus3db"][0] - 100) < 2,
            "causal: -3 dB lands on the nominal cutoff", str(d["minus3db"][:1]))

    # filtfilt squares the response, so -3 dB moves inside the cutoff. This is
    # the discrepancy the overlay exists to show.
    st, z = post(base, "/api/filter/response",
                 {"fs": fs, "lp_cutoff": 100, "lp_order": 4, "zero_phase": "true"})
    if r.check(st == 200, "zero-phase response returns"):
        r.check(z["minus3db"] and z["minus3db"][0] < 100,
                "zero-phase: -3 dB moves inside the nominal cutoff",
                f"{z['minus3db'][0]:.1f} Hz vs nominal 100")
        r.check(z["effective_order"]["lp"] == 8, "and the effective order is doubled",
                str(z["effective_order"]))

    # Band-pass: low gain outside, near unity inside.
    st, bp = post(base, "/api/filter/response",
                  {"fs": fs, "hp_cutoff": 50, "lp_cutoff": 200, "zero_phase": "true"})
    if st == 200:
        gain_at = lambda f0: min(  # noqa: E731
            zip(bp["freqs"], bp["magnitude"]), key=lambda p: abs(p[0] - f0))[1]
        r.check(gain_at(125) > 0.9 and gain_at(10) < 0.1 and gain_at(400) < 0.1,
                "band-pass passes the middle and rejects both sides",
                f"10Hz={gain_at(10):.3f} 125Hz={gain_at(125):.3f} 400Hz={gain_at(400):.3f}")

    st, none = post(base, "/api/filter/response", {"fs": fs})
    r.check(st == 200 and not none.get("applied"),
            "no filter reports applied=false, so nothing is drawn")


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


def test_correlation_echoes_normalization(base, sess, r):
    """The y-axis units depend on it, so the payload has to state it."""
    r.section("ACF and CCF say whether they were normalized")
    f = base_fields(sess, [1, 2])

    for norm in (True, False):
        st, d = post(base, "/api/spectral/autocorrelation", {**f, "normalize": norm})
        r.check(st == 200 and d.get("normalized") is norm,
                f"autocorrelation echoes normalized={norm}", f"{st} {d.get('normalized')!r}")

        st, d = post(base, "/api/spectral/cross_correlation",
                     {**f, "signal_col_x": 1, "signal_col_y": 2, "normalize": norm})
        r.check(st == 200 and d.get("normalized") is norm,
                f"cross_correlation echoes normalized={norm}", f"{st} {d.get('normalized')!r}")

    # A normalized ACF peaks at 1.0 at zero lag; an unnormalized one does not.
    # This is what makes the flag worth trusting rather than merely echoing.
    st, d = post(base, "/api/spectral/autocorrelation", {**f, "normalize": True})
    peak = max(d["signals"][0]["acf"]) if st == 200 else None
    r.check(peak is not None and abs(peak - 1.0) < 1e-6,
            "a normalized ACF really does peak at 1.0", f"{peak!r}")


def main(base):
    r = Results()
    print(f"API tests against {base}")
    sess = make_session(base, r)
    test_overview(base, sess, r)
    test_fdd_needs_response_channels(base, sess, r)
    test_fanout(base, sess, r)
    test_single_channel(base, sess, r)
    test_preprocessing_reaches_analyses(base, sess, r)
    test_filter_options(base, sess, r)
    test_filter_response(base, sess, r)
    test_correlation_echoes_normalization(base, sess, r)
    test_session_errors(base, sess, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
