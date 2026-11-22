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
    # max_points=0 turns the display thinning off. It matters here: the series
    # the chart is sent keeps the min and max of each bin and drops everything
    # between, so its mean is not the signal's mean. Any check that reads a
    # *statistic* off this endpoint has to ask for the real thing.
    fg = {**base_fields(sess, [3]), "max_points": 0}   # force1 has a non-zero mean
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


def test_surface_decimation_and_clock(base, sess, r):
    """What the Explorer needs from the timefreq endpoints."""
    r.section("time-frequency surfaces: size and time origin")
    f = base_fields(sess, [1])
    tf = {**f, "signal_col": 1}

    st, full = post(base, "/api/timefreq/stft", {**tf, "window": "hann", "nperseg": 256})
    r.check(st == 200, "STFT without limits still works", str(st))

    st, small = post(base, "/api/timefreq/stft",
                     {**tf, "window": "hann", "nperseg": 256,
                      "max_freq": 40, "max_time": 50})
    r.check(st == 200, "STFT accepts decimation limits", str(st))
    if st == 200:
        r.check(len(small["freqs"]) <= 40 and len(small["times"]) <= 50,
                "the surface is capped to the requested grid",
                f"{len(small['freqs'])} x {len(small['times'])}")
        r.check(len(small["magnitude"]) == len(small["freqs"]),
                "rows still match the frequency axis")
        r.check(len(small["magnitude"][0]) == len(small["times"]),
                "columns still match the time axis")
        r.check(len(small["freqs"]) < len(full["freqs"]),
                "and it really is smaller than the undecimated one")

        # Peak-preserving, not striding: the loudest bin must survive being
        # thinned, or a one-bin ridge would vanish from the display.
        peak_full = max(max(row) for row in full["magnitude"])
        peak_small = max(max(row) for row in small["magnitude"])
        r.check(abs(peak_small - peak_full) < peak_full * 1e-9,
                "the peak magnitude survives decimation",
                f"{peak_small:.6g} vs {peak_full:.6g}")

    # Every panel of the Explorer shares one x-axis, so a windowed transform
    # must report the record's own clock rather than restarting at zero.
    r.section("a windowed surface stays on the record's clock")
    win = "?win_start=9216&win_end=11264&win_unit=samples"
    st, w_ts = post(base, "/api/signal/timeseries" + win, f)
    st2, w_tf = post(base, "/api/timefreq/stft" + win,
                     {**tf, "window": "hann", "nperseg": 256})
    if st == 200 and st2 == 200:
        t_ts = w_ts["times_proc"]
        r.check(abs(t_ts[0] - w_tf["times"][0]) < 0.01,
                "the surface and the time series start at the same instant",
                f"ts {t_ts[0]:.3f} vs stft {w_tf['times'][0]:.3f}")
        r.check(w_tf["times"][0] > 1.0,
                "and that instant is the window's, not zero",
                f"{w_tf['times'][0]:.3f} s")


def test_fsst_sharpens_the_stft(base, sess, r):
    """FSST must be reachable, aligned with the STFT, and actually sharper."""
    r.section("synchrosqueezing")
    f = base_fields(sess, [1])
    common = {**f, "signal_col": 1, "window": "hann", "nperseg": 512}

    st, a = post(base, "/api/timefreq/stft", common)
    st2, b = post(base, "/api/timefreq/fsst", common)
    r.check(st2 == 200, "the FSST endpoint answers", str(st2))
    if st != 200 or st2 != 200:
        return

    r.check(a["freqs"] == b["freqs"],
            "FSST squeezes onto the STFT's own frequency grid",
            f"{len(a['freqs'])} vs {len(b['freqs'])}")

    # Frames lie wholly inside the signal, so the axis starts half a window in
    # rather than at zero -- the documented difference from stft().
    half = 512 / 2 / sess["fs"]
    r.check(abs(b["times"][0] - half) < 0.01,
            "and starts half a window in, since it does not pad",
            f"{b['times'][0]:.3f} s, expected {half:.3f}")

    def ridge_width(payload, f0, span=6.0):
        freqs = payload["freqs"]
        prof = [sum(row) for row in payload["magnitude"]]
        band = [(fq, pv) for fq, pv in zip(freqs, prof) if abs(fq - f0) <= span]
        peak = max(pv for _, pv in band)
        hit = [fq for fq, pv in band if pv >= peak / 2]
        return max(hit) - min(hit)

    # 10 Hz is the mode with room to sharpen; the 25 Hz one already sits at the
    # bin spacing for this nperseg, so there is nothing left to concentrate.
    wa, wb = ridge_width(a, 10.0), ridge_width(b, 10.0)
    r.check(wb < wa, "the 10 Hz ridge is narrower than the STFT's",
            f"STFT {wa:.2f} Hz -> FSST {wb:.2f} Hz")

    # The point of squeezing: more of the plane ends up empty.
    def empty_fraction(payload):
        rows = payload["magnitude"]
        peak = max(max(row) for row in rows)
        n = sum(len(row) for row in rows)
        return sum(1 for row in rows for v in row if v < 0.01 * peak) / n
    r.check(empty_fraction(b) > empty_fraction(a),
            "and more of the surface is empty than before",
            f"{empty_fraction(a):.1%} -> {empty_fraction(b):.1%}")

    st, _ = post(base, "/api/timefreq/fsst", {**common, "nperseg": 999999})
    r.check(st == 422, "a segment longer than the record is refused", str(st))


def test_error_spectrum(base, sess, r):
    """The Predictability tab's third mode: what the other channels cannot explain.

    The example file is a 2DOF chain driven by force1 and force2, so predicting
    x1_disp from both forces is the case where a linear model is *exactly*
    right: the true unexplained share is zero. That makes this file a live
    demonstration of the resolution trap rather than a happy path. Its modes
    sit at 8.6 and 20.8 Hz with about 4.6% damping, so the sharpest half-power
    bandwidth is near 0.8 Hz, and the default nperseg of 1024 at fs = 1024
    resolves to about 1.5 Hz -- roughly eight times coarser than the classical
    criterion allows. The leakage that follows fabricates an error spectrum.
    """
    r.section("Error spectrum")

    def run(cols, target, nperseg=1024):
        return post(base, "/api/multisensor/coherence_conditioned",
                    {**base_fields(sess, cols), "mode": "error",
                     "target_col": target, "nperseg": nperseg, "window": "hann"})

    st, d = run([1, 3, 4], 1)
    r.check(st == 200, "error mode returns 200", str(st))
    if st != 200:
        return

    r.check(d["target"] == "x1_disp" and d["predictors"] == ["force1", "force2"],
            "the target is named and the rest become predictors",
            f"{d['target']} <- {d['predictors']}")

    n = len(d["freqs"])
    r.check(all(len(d[k]) == n for k in
                ("target_psd", "error_spectrum", "coherence", "input_condition")),
            "every curve is on the same frequency grid", f"{n} bins")

    # The identity the whole thing rests on: the two parts must sum to the total.
    worst = max(abs(e + c * s - s) / s if s > 0 else 0.0
                for e, c, s in zip(d["error_spectrum"], d["coherence"],
                                   d["target_psd"]))
    r.check(worst < 1e-9,
            "coherent power and error spectrum sum back to the target PSD",
            f"worst relative error {worst:.1e}")

    # The true answer is zero, so everything reported here is estimation bias,
    # and it has to shrink as the segments lengthen past the mode bandwidth.
    fracs = []
    for nps in (1024, 4096, 8192):
        stn, dn = run([1, 3, 4], 1, nperseg=nps)
        if stn != 200:
            r.check(False, f"error mode at nperseg={nps}", str(stn))
            return
        fracs.append(dn["unexplained_fraction"])
    r.check(fracs[0] > fracs[1] > fracs[2],
            "the fabricated residual shrinks as the segments resolve the modes",
            " -> ".join(f"{100 * v:.1f}%" for v in fracs))
    r.check(fracs[-1] < 0.02,
            "and nearly vanishes once the resolution criterion is met",
            f"{100 * fracs[-1]:.2f}% unexplained")

    # The sharpest way to say why this matters: at the default segment length
    # the *wrong* model wins, and only adequate resolution reverses it.
    st2, d2 = run([1, 2], 1)
    r.check(st2 == 200 and d2["unexplained_fraction"] < fracs[0],
            "at the default nperseg a proxy channel beats the true inputs",
            f"x2 {100 * d2['unexplained_fraction']:.1f}% vs "
            f"forces {100 * fracs[0]:.1f}%")

    st3, d3 = run([1, 2], 1, nperseg=8192)
    r.check(st3 == 200 and fracs[-1] < d3["unexplained_fraction"],
            "and the ordering rights itself once the modes are resolved",
            f"forces {100 * fracs[-1]:.1f}% vs "
            f"x2 {100 * d3['unexplained_fraction']:.1f}%")

    r.check(len(d2["ordinary_coherence"]) == 1
            and d2["ordinary_coherence"][0]["name"] == "x2_disp",
            "each predictor's own coherence comes back labelled")

    # Resolving the modes on a 20-second record costs nearly all the averages,
    # which is the squeeze this file cannot escape: the same call that fixes
    # the resolution bias raises the bias floor to 0.5. The library says so and
    # the API has to pass that on rather than let it die in the log.
    st4, d4 = run([1, 3, 4], 1, nperseg=8192)
    r.check(st4 == 200 and d4["notes"],
            "a large bias floor is reported to the panel, not swallowed",
            (d4.get("notes") or ["<none>"])[0][:60] + "…")
    r.check(st4 == 200 and d4["bias_floor"] > d["bias_floor"],
            "and the floor itself is returned so the plot can draw it",
            f"{d4['bias_floor']:.3f} vs {d['bias_floor']:.3f}")

    st5, _ = run([1, 3, 4], 2)
    r.check(st5 == 422, "a target outside the selection is refused", str(st5))

    st6, _ = run([1], 1)
    r.check(st6 == 422, "one channel alone is refused", str(st6))

    # The other two modes must be untouched by the new branch.
    st7, d7 = post(base, "/api/multisensor/coherence_conditioned",
                   {**base_fields(sess, [1, 2, 3]), "mode": "multiple",
                    "nperseg": 1024, "window": "hann"})
    r.check(st7 == 200 and len(d7.get("signals", [])) == 3,
            "multiple coherence still works as before")

    st8, _ = post(base, "/api/multisensor/coherence_conditioned",
                  {**base_fields(sess, [1, 2]), "mode": "multiple",
                   "nperseg": 1024, "window": "hann"})
    r.check(st8 == 422, "and still needs three channels", str(st8))


def test_display_thinning(base, sess, r):
    """Endpoints thin for the chart, and say so, without losing the peaks.

    The example file is 20,480 samples, so the default budget bites. Three
    properties have to hold together, and the third is the one that makes the
    thinning safe rather than merely small: extremes survive, so a resonance or
    a transient cannot vanish from the plot.
    """
    r.section("Display thinning")
    f = base_fields(sess, [1, 2])

    st, thin = post(base, "/api/signal/timeseries", f)
    st2, full = post(base, "/api/signal/timeseries", {**f, "max_points": 0})
    if not r.check(st == 200 and st2 == 200, "timeseries responds both ways"):
        return

    r.check(thin["decimated"] is True and full["decimated"] is False,
            "the response says whether it was thinned",
            f"{len(thin['times_proc'])} vs {len(full['times_proc'])} points")
    r.check(len(thin["times_proc"]) < len(full["times_proc"]) / 2,
            "and the thinned one is much smaller",
            f"{len(thin['times_proc'])} vs {len(full['times_proc'])}")
    r.check(thin["n_total"] == full["n_total"] == sess["n_samples"],
            "both still report the true sample count, so the chart can say so")

    # The property that matters: nothing is lost off the top or the bottom.
    for i in (0, 1):
        a = thin["signals"][i]["signal_proc"]
        b = full["signals"][i]["signal_proc"]
        r.check(abs(max(a) - max(b)) < 1e-9 and abs(min(a) - min(b)) < 1e-9,
                f"channel {i}: the extremes survive thinning",
                f"max {max(a):.6g} vs {max(b):.6g}")

    # The budget is for the whole chart, not per channel: four channels whose
    # extremes fall in different places used to come back at up to 4x it.
    st, many = post(base, "/api/signal/timeseries", base_fields(sess, [1, 2, 3, 4]))
    if st == 200:
        r.check(len(many["times_proc"]) <= 8000,
                "several channels share one point budget",
                f"{len(many['times_proc'])} points per channel for 4 channels")
        for i in range(4):
            a = many["signals"][i]["signal_proc"]
            st_f, one = post(base, "/api/signal/timeseries",
                             {**base_fields(sess, [i + 1]), "max_points": 0})
            b = one["signals"][0]["signal_proc"]
            r.check(abs(max(a) - max(b)) < 1e-9 and abs(min(a) - min(b)) < 1e-9,
                    f"and channel {i + 1} still keeps its extremes")

    # x must stay ascending or the line doubles back on itself.
    t = thin["times_proc"]
    r.check(all(t[i] <= t[i + 1] for i in range(len(t) - 1)),
            "the thinned time axis is still ascending")

    st, ffull = post(base, "/api/spectral/fft", {**f, "window": "hann",
                                                "scaling": "amplitude",
                                                "max_points": 0})
    st, fthin = post(base, "/api/spectral/fft", {**f, "window": "hann",
                                                "scaling": "amplitude"})
    if r.check(st == 200, "fft responds"):
        r.check(len(fthin["freqs"]) < len(ffull["freqs"]),
                "fft thins its bins too",
                f"{len(fthin['freqs'])} of {fthin['n_bins']} bins")
        pf = max(ffull["signals"][0]["amplitude"])
        pt = max(fthin["signals"][0]["amplitude"])
        r.check(abs(pf - pt) < 1e-9,
                "and the tallest peak is exactly the one the full spectrum has",
                f"{pt:.6g} vs {pf:.6g}")
        r.check(len(fthin["signals"][0]["phase"]) == len(fthin["freqs"]),
                "phase comes back on the same bins as amplitude, not its own")


def test_show_original_toggle(base, sess, r):
    """The ghost trace is the larger half of the payload; it must be optional."""
    r.section("Show original toggle")
    f = base_fields(sess, [1, 2])
    q = "?target_fs=200"          # resampling is where the raw copy dominates

    st, on = post(base, "/api/signal/timeseries" + q, {**f, "include_raw": "true"})
    st2, off = post(base, "/api/signal/timeseries" + q, {**f, "include_raw": "false"})
    if not r.check(st == 200 and st2 == 200, "both variants respond"):
        return

    r.check(on["times_raw"] is not None and on["signals"][0]["signal_raw"] is not None,
            "with it on, the original comes back")
    r.check(off["times_raw"] is None and off["signals"][0]["signal_raw"] is None,
            "with it off, it is absent rather than empty")
    r.check(len(json.dumps(off)) < len(json.dumps(on)),
            "so the response is smaller",
            f"{len(json.dumps(off)) / 1000:.0f} kB vs {len(json.dumps(on)) / 1000:.0f} kB")
    r.check(off["signals"][0]["signal_proc"] == on["signals"][0]["signal_proc"],
            "and the processed trace is untouched by the toggle")

    # Without preprocessing there is no ghost: the plotted trace goes once,
    # under the processed names, rather than twice under both.
    st, plain = post(base, "/api/signal/timeseries", {**f, "include_raw": "true"})
    r.check(st == 200 and plain["times_raw"] is None
            and plain["signals"][0]["signal_raw"] is None
            and plain["signals"][0]["signal_proc"] is not None,
            "with no preprocessing the trace is sent once, not twice")


def test_zoom_window_buys_resolution(base, sess, r):
    """A view window spends the same budget on a shorter span."""
    r.section("Zoom window")
    f = base_fields(sess, [1])

    st, whole = post(base, "/api/signal/timeseries", f)
    st2, win = post(base, "/api/signal/timeseries",
                    {**f, "view_start": 5.0, "view_end": 5.5})
    if not r.check(st == 200 and st2 == 200, "windowed request responds"):
        return

    tw = win["times_proc"]
    r.check(tw[0] >= 4.9 and tw[-1] <= 5.6,
            "only the asked-for window comes back",
            f"{tw[0]:.3f}-{tw[-1]:.3f} s")
    # Mean spacing, not the first gap: min/max thinning emits two neighbouring
    # samples per bin, so the first gap is one sample period however coarse the
    # thinning is. Averaging over the record is what actually measures density.
    def mean_dt(t):
        return (t[-1] - t[0]) / (len(t) - 1)
    dt_whole, dt_win = mean_dt(whole["times_proc"]), mean_dt(tw)
    r.check(dt_win < dt_whole,
            "and it is sampled more finely than the whole record",
            f"{dt_win:.3g} s vs {dt_whole:.3g} s")
    r.check(win["decimated"] is False,
            "half a second at 1024 Hz fits the budget, so it is not thinned at all")


def test_ar_spectrum(base, sess, r):
    """The PSD tab's second method: a model fit rather than averaged segments."""
    r.section("AR spectrum")
    f = base_fields(sess, [1, 2])

    st, welch = post(base, "/api/spectral/psd",
                     {**f, "window": "hann", "nperseg": 1024, "scaling": "density"})
    st2, ar = post(base, "/api/spectral/psd", {**f, "method": "ar", "ar_order": 40})
    if not r.check(st == 200 and st2 == 200, "both methods respond", f"{st}/{st2}"):
        return

    r.check(welch["method"] == "welch" and ar["method"] == "ar",
            "each response says which method produced it")
    r.check(all(sg["order"] == 40 for sg in ar["signals"]),
            "the order is echoed per channel, because it decides what the curve says")
    r.check(all(sg["stable"] for sg in ar["signals"]),
            "and the fitted model is stable")

    # Different estimators of the same quantity must agree on total power.
    def power(d, key):
        f_, y = d["freqs"], d["signals"][0][key]
        return sum((y[i] + y[i + 1]) / 2 * (f_[i + 1] - f_[i])
                   for i in range(len(f_) - 1))
    pw, pa = power(welch, "Pxx"), power(ar, "Pxx")
    r.check(abs(pa - pw) / pw < 0.25,
            "and integrate to the same power as Welch, within a quarter",
            f"{pa:.4g} vs {pw:.4g}")

    st, auto = post(base, "/api/spectral/psd",
                    {**f, "method": "ar", "ar_order": 0, "ar_criterion": "bic"})
    r.check(st == 200 and auto["ar_selected"] == "bic"
            and all(sg["order"] > 1 for sg in auto["signals"]),
            "order 0 means choose one, and the criterion used is reported",
            f"orders {auto['ar_orders']}")

    st, bad = post(base, "/api/spectral/psd",
                   {**f, "method": "ar", "ar_order": 999999})
    r.check(st == 422, "an impossible order is refused, not clipped", str(st))


def test_segment_advice(base, sess, r):
    """The nperseg trade, weighed in both directions on the actual record."""
    r.section("Segment advice")
    f = base_fields(sess, [1])

    st, coarse = post(base, "/api/spectral/segment_advice",
                      {**f, "nperseg": 256, "window": "hann"})
    st2, longer = post(base, "/api/spectral/segment_advice",
                       {**f, "nperseg": 8192, "window": "hann"})
    if not r.check(st == 200 and st2 == 200, "advice responds", f"{st}/{st2}"):
        return

    r.check(coarse["resolution_bw"] > longer["resolution_bw"],
            "a shorter segment has a wider resolution bandwidth",
            f"{coarse['resolution_bw']:.3g} vs {longer['resolution_bw']:.3g} Hz")
    r.check(coarse["n_segments"] > longer["n_segments"],
            "and more averages — the trade, in one pair of numbers",
            f"{coarse['n_segments']} vs {longer['n_segments']}")
    r.check(longer["bias_floor"] > coarse["bias_floor"],
            "so the coherence bias floor moves the other way",
            f"{coarse['bias_floor']:.3f} -> {longer['bias_floor']:.3f}")
    r.check(bool(coarse["advice"]) and coarse["verdict"] in
            ("ok", "marginal", "unresolved", "too_few", "squeezed"),
            "each answer carries a verdict and a sentence saying what to change",
            coarse["verdict"])
    r.check(coarse.get("channel") == "x1_disp",
            "and names the channel it looked at")

    # The resolution bandwidth is a window property, not a guess.
    st, flat = post(base, "/api/spectral/segment_advice",
                    {**f, "nperseg": 1024, "window": "flattop"})
    st, hann = post(base, "/api/spectral/segment_advice",
                    {**f, "nperseg": 1024, "window": "hann"})
    r.check(flat["resolution_bw"] > hann["resolution_bw"] * 2,
            "a flat-top window is much wider than a Hann, as its ENBW says",
            f"{flat['resolution_bw']:.3g} vs {hann['resolution_bw']:.3g} Hz")


def test_mat_file(base, sess, r):
    """A .mat upload: rate, names and axis come from the file, not from guessing."""
    import io as _io

    import numpy as np
    import scipy.io as sio

    r.section(".mat files")
    rows = [l.split(",") for l in CSV.read_text().splitlines()[1:] if l.strip()]
    data = np.array(rows, dtype=float)[:, 1:3]  # x1_disp, x2_disp; samples down
    buf = _io.BytesIO()
    sio.savemat(buf, {"data": data, "fs": 1024.0,
                      "labels": np.array(["x1_disp", "x2_disp"], dtype=object),
                      "t0": "2019-01-01T00:00:00"})
    st, m = post(base, "/api/session/create", {}, {"file": ("rec.mat", buf.getvalue())})
    r.check(st == 200, "session/create accepts a .mat file", str(st) if st != 200 else "")
    if st != 200:
        return
    r.check(m["column_names"] == ["x1_disp", "x2_disp"], "channel names come from labels",
            str(m["column_names"]))
    r.check(m["n_samples"] == 20480 and m["n_columns"] == 2,
            "samples run along the long axis", f"{m['n_columns']} x {m['n_samples']}")
    r.check(m["time_col"] == -1 and abs(m["fs"] - 1024) < 1e-6,
            "fs is read from the file, with no time column", str(m.get("fs")))
    det = m["detected"]
    r.check(det["format"] == "mat" and det["t0"] == "2019-01-01T00:00:00"
            and det["mat_sources"]["fs"] == "fs",
            "detection reports the format, start time and variables used", str(det))

    f = {**base_fields(m, [0, 1]), "window": "hann", "nperseg": 1024, "scaling": "density"}
    st, psd = post(base, "/api/spectral/psd", f)
    r.check(st == 200 and len(psd.get("signals", [])) == 2, "analyses run on a .mat session")

    st, bad = post(base, "/api/session/create", {},
                   {"file": ("bad.mat", b"MATLAB 7.3 MAT-file".ljust(512) + bytes([0x89]) + b"HDF" + bytes([13, 10, 26, 10]))})
    r.check(st == 422 and "-v7" in str(bad), "a v7.3 file is refused with advice", str(st))


def test_zoom_windows(base, sess, r):
    """Every thinned chart re-spends its budget on the zoomed window."""
    r.section("Zoom windows on every thinned endpoint")
    one = base_fields(sess, [1])
    pair = {k: v for k, v in one.items() if k != "signal_cols"}
    cases = [
        ("timeseries", "/api/signal/timeseries", {**one}, "times_proc"),
        ("autocorrelation", "/api/spectral/autocorrelation", {**one}, "lags"),
        ("filter", "/api/filter/apply",
         {**pair, "signal_col": 1, "filter_type": "lowpass", "cutoff": 50}, "times"),
        ("instantaneous", "/api/instantaneous", {**pair, "signal_col": 1}, "times"),
        ("cross-correlation", "/api/spectral/cross_correlation",
         {**pair, "signal_col_x": 1, "signal_col_y": 2}, "lags"),
    ]
    step = 1 / sess["fs"]
    for name, ep, fields, axis in cases:
        f = {**fields, "max_points": 1000}
        st, full = post(base, ep, f)
        st2, z = post(base, ep, {**f, "view_start": 2.0, "view_end": 2.5})
        if not r.check(st == 200 and st2 == 200, f"{name} responds", f"{st} {st2}"):
            continue
        x = z[axis]
        steps = [b - a for a, b in zip(x, x[1:])]
        r.check(full["decimated"], f"{name}: the whole record is thinned")
        r.check(not z["decimated"] and z["view"] == [2.0, 2.5]
                and max(abs(d - step) for d in steps) < 0.01 * step,
                f"{name}: a 0.5 s window comes back at every sample", f"{len(x)} points")


def test_fft_zoom_window(base, sess, r):
    """Zooming the FFT re-spends the budget on the band: every bin, at 1/T."""
    r.section("FFT zoom window")
    f = {**base_fields(sess, [1, 2]), "window": "hann", "scaling": "amplitude",
         "max_points": 2000}
    st, full = post(base, "/api/spectral/fft", f)
    if not r.check(st == 200, "fft responds", str(st)):
        return
    T = sess["n_samples"] / sess["fs"]
    r.check(abs(full["df"] - 1 / T) < 1e-9, "df is 1 / duration",
            f"{full['df']:.6f} vs {1 / T:.6f}")
    r.check(full["decimated"] and full["view"] is None,
            "the whole band is thinned and has no view")

    st, z = post(base, "/api/spectral/fft", {**f, "view_start": 10, "view_end": 20})
    if not r.check(st == 200, "windowed fft responds", str(st)):
        return
    fr = z["freqs"]
    steps = [b - a for a, b in zip(fr, fr[1:])]
    r.check(not z["decimated"] and z["view"] == [10, 20],
            "a 10 Hz window fits the budget and echoes the view")
    r.check(fr[0] <= 10 and fr[-1] >= 20 and fr[1] > 10 and fr[-2] < 20,
            "the window spans the band, one bin past each edge")
    r.check(max(abs(d - full["df"]) for d in steps) < 1e-9,
            "every bin in the window is sent", f"{len(fr)} bins")


def test_resample_anti_alias(base, r):
    """Resampling down removes what would fold into the band, not just thins it."""
    import io as _io

    import numpy as np
    import scipy.io as sio

    r.section("Resample anti-aliasing")
    fs = 1024.0
    t = np.arange(int(20 * fs)) / fs
    # A 2 Hz signal under a strong 330 Hz line. At 100 Hz, 330 folds to 30 Hz.
    x = np.sin(2 * np.pi * 2 * t) + 5 * np.sin(2 * np.pi * 330 * t)
    buf = _io.BytesIO()
    sio.savemat(buf, {"data": np.c_[x, x], "fs": fs})
    st, m = post(base, "/api/session/create", {}, {"file": ("tone.mat", buf.getvalue())})
    if not r.check(st == 200, "session from a synthetic record"):
        return

    st, psd = post(base, "/api/spectral/psd?target_fs=100",
                   {**base_fields(m, [0]), "window": "hann", "nperseg": 512,
                    "scaling": "density"})
    if not r.check(st == 200, "psd after resampling to 100 Hz responds", str(st)):
        return
    f, p = psd["freqs"], psd["signals"][0]["Pxx"]
    at = lambda f0: max(p[i] for i in range(len(f)) if abs(f[i] - f0) < 1.0)  # noqa: E731
    r.check(at(30) < 1e-4 * at(2),
            "the 330 Hz line does not fold to 30 Hz",
            f"30 Hz / 2 Hz power ratio {at(30) / at(2):.2e}")


def test_spectral_cube_endpoints(base, sess, r):
    """PSD, CSD, coherence, the coherence matrix and FDD all read one cached
    cross-spectral matrix (DSPkit spectral_cube). They must agree with each
    other exactly, whichever request built the cube."""
    r.section("Spectral endpoints share one cross-spectral matrix")
    f = base_fields(sess, [1, 2, 3, 4])
    sp = {"window": "hann", "nperseg": 1024}
    st, fdd = post(base, "/api/fdd/analyze", {**f, **sp})          # builds the cube
    st2, psd = post(base, "/api/spectral/psd", {**f, **sp, "scaling": "density"})
    r.check(st == 200 and st2 == 200, "FDD then PSD on the same cube")
    st, sub = post(base, "/api/spectral/psd",
                   {**base_fields(sess, [3, 1]), **sp, "scaling": "density"})
    r.check(st == 200 and sub["signals"][0]["Pxx"] == psd["signals"][2]["Pxx"]
            and sub["signals"][1]["Pxx"] == psd["signals"][0]["Pxx"],
            "a subset in another order is served from the same cube")
    st, self_csd = post(base, "/api/spectral/csd",
                        {**f, **sp, "signal_col_x": 2, "signal_col_y": 2})
    p2 = psd["signals"][1]["Pxx"]
    r.check(st == 200 and max(abs(a - b) for a, b in zip(self_csd["magnitude"], p2))
            <= 1e-9 * max(p2), "CSD of a channel with itself is its PSD")
    st, coh = post(base, "/api/spectral/coherence",
                   {**f, **sp, "signal_col_x": 1, "signal_col_y": 3})
    st2, cm = post(base, "/api/multisensor/coherence_matrix", {**f, **sp})
    pair = next(p for p in cm["pairs"] if p["label"].startswith("x1_disp") and "force1" in p["label"])
    r.check(st == 200 and st2 == 200 and
            max(abs(a - b) for a, b in zip(coh["Cxy"], pair["Cxy"])) < 1e-12,
            "pair coherence equals its entry in the coherence matrix")
    st, spec = post(base, "/api/spectral/psd", {**f, **sp, "scaling": "spectrum"})
    ratio = [a / b for a, b in zip(spec["signals"][0]["Pxx"], psd["signals"][0]["Pxx"]) if b > 0]
    r.check(st == 200 and max(ratio) - min(ratio) < 1e-9 * max(ratio),
            "power spectrum is the density times one constant (the window's ENBW)",
            f"{ratio[0]:.4g}")
    st, fdd2 = post(base, "/api/fdd/analyze", {**f, **sp})
    r.check(st == 200 and fdd2["S"] == fdd["S"], "FDD again from the cache is identical")


def test_windowed_statistics(base, sess, r):
    r.section("Windowed statistics")
    f = base_fields(sess, [1])
    st, d = post(base, "/api/indicators", {**f, "signal_col": 1, "segment_duration": 2.0})
    keys = ["times", "w_rms", "w_mean", "w_peak", "w_crest", "w_kurtosis",
            "w_dominant_freq", "w_entropy"]
    r.check(st == 200 and all(len(d[k]) == d["n_windows"] for k in keys),
            "one value per window in every series", str(d.get("n_windows")))
    r.check(st == 200 and d["n_windows"] == 10 and abs(d["window_duration"] - 2.0) < 1e-3,
            "20 s record in 2 s windows gives 10", f"{d.get('window_duration')}")
    r.check(all(c >= 1.0 for c in d["w_crest"]), "crest factor is at least 1")
    r.check(all(0.0 <= e <= 1.0 for e in d["w_entropy"]), "spectral entropy in [0, 1]")
    st, d3 = post(base, "/api/indicators",
                  {**f, "signal_col": 1, "segment_duration": 2.0, "excess": "false"})
    r.check(st == 200 and all(abs(a + 3 - b) < 1e-9 for a, b in zip(d["w_kurtosis"], d3["w_kurtosis"])),
            "plain kurtosis is excess + 3")
    st, auto = post(base, "/api/indicators", {**f, "signal_col": 1})
    r.check(st == 200 and auto["n_windows"] == 100, "default: 100 windows", str(auto.get("n_windows")))


def test_engine_stop_needs_supervisor(base, r):
    """The test backend is plain uvicorn: nothing would restart it, so the
    stop route must refuse instead of killing the server."""
    r.section("Force stop")
    st, d = post(base, "/api/engine/stop", {})
    r.check(st == 409, "refused when not started by run.py", str(st))
    from http_util import get
    st, h = get(base, "/api/health")
    r.check(st == 200 and h.get("restartable") is False, "server still up, reports not restartable")


def main(base):
    r = Results()
    print(f"API tests against {base}")
    sess = make_session(base, r)
    test_overview(base, sess, r)
    test_fft_zoom_window(base, sess, r)
    test_zoom_windows(base, sess, r)
    test_fdd_needs_response_channels(base, sess, r)
    test_fanout(base, sess, r)
    test_single_channel(base, sess, r)
    test_preprocessing_reaches_analyses(base, sess, r)
    test_filter_options(base, sess, r)
    test_filter_response(base, sess, r)
    test_correlation_echoes_normalization(base, sess, r)
    test_surface_decimation_and_clock(base, sess, r)
    test_fsst_sharpens_the_stft(base, sess, r)
    test_error_spectrum(base, sess, r)
    test_display_thinning(base, sess, r)
    test_show_original_toggle(base, sess, r)
    test_zoom_window_buys_resolution(base, sess, r)
    test_ar_spectrum(base, sess, r)
    test_segment_advice(base, sess, r)
    test_mat_file(base, sess, r)
    test_resample_anti_alias(base, r)
    test_session_errors(base, sess, r)
    test_spectral_cube_endpoints(base, sess, r)
    test_windowed_statistics(base, sess, r)
    test_engine_stop_needs_supervisor(base, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
