"""Detection must say *why* it refused a time column.

Returning only "no time column" meant a record with one dropped sample was
indistinguishable from one with no time axis at all, and both were analysed at
the manual default of 1000 Hz — silently rescaling every frequency axis.

Run via `python tests/run_all.py`, or standalone against a running backend:

    python tests/api/test_detect.py http://127.0.0.1:8000
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from http_util import Results, post  # noqa: E402

FS = 1000.0
N = 4000


def csv_bytes(times, n_channels=2):
    """A tiny multi-channel CSV with the given time column."""
    out = io.StringIO()
    out.write("time," + ",".join(f"x{i}" for i in range(n_channels)) + "\n")
    for i, t in enumerate(times):
        vals = ",".join(f"{(i % 17) * 0.01 + c:.6f}" for c in range(n_channels))
        out.write(f"{t:.9f},{vals}\n")
    return out.getvalue().encode()


def clean_times():
    return [i / FS for i in range(N)]


def dropped_sample_times():
    """One missing sample halfway: a single interval of 2/FS."""
    t = clean_times()
    return [x + (1 / FS if i >= N // 2 else 0) for i, x in enumerate(t)]


def jittery_times():
    """Pervasively irregular — every interval differs."""
    t, acc = [], 0.0
    for i in range(N):
        t.append(acc)
        acc += (1 / FS) * (0.7 + 0.6 * ((i * 7919 % 1000) / 1000.0))
    return t


def backwards_times():
    """Strictly increasing except for one step back — a clock reset."""
    t = clean_times()
    t[N // 2] = t[N // 4]
    return t


def open_csv(base, raw, name):
    return post(base, "/api/session/create", {}, {"file": (name, raw)})


def test_clean_file_still_detects(base, r):
    r.section("a clean time column is unaffected")
    st, s = open_csv(base, csv_bytes(clean_times()), "clean.csv")
    if not r.check(st == 200, "clean file loads", str(st)):
        return
    r.check(s["time_col"] == 0, "time column found", str(s["time_col"]))
    r.check(abs(s.get("fs", 0) - FS) < 1, "fs read from it", str(s.get("fs")))
    r.check(s["detected"].get("time_col_rejected") is None,
            "nothing is reported as rejected")


def test_dropped_sample(base, r):
    r.section("one dropped sample")
    st, s = open_csv(base, csv_bytes(dropped_sample_times()), "dropout.csv")
    if not r.check(st == 200, "file loads", str(st)):
        return
    r.check(s["time_col"] == -1, "the column is still refused", str(s["time_col"]))
    rej = s["detected"].get("time_col_rejected")
    if not r.check(rej is not None, "but the refusal is reported"):
        return
    r.check(rej["reason"] == "non_uniform", "reason is non-uniform", rej["reason"])
    r.check(rej["col"] == 0, "and names the column", str(rej["col"]))
    r.check(rej["n_irregular"] == 1,
            "exactly one interval is irregular -- a gap, not jitter",
            str(rej["n_irregular"]))
    r.check(abs(rej["implied_fs"] - FS) < 1,
            "the true rate is still recoverable from the median",
            f"{rej['implied_fs']:.3f} Hz")
    r.check(abs(rej["max_dt"] - 2 / FS) < 1e-9,
            "the gap shows up as a doubled interval", f"{rej['max_dt']:.6f}")


def test_jitter(base, r):
    r.section("pervasive jitter")
    st, s = open_csv(base, csv_bytes(jittery_times()), "jitter.csv")
    if not r.check(st == 200, "file loads", str(st)):
        return
    rej = s["detected"].get("time_col_rejected")
    if not r.check(rej is not None, "the refusal is reported"):
        return
    r.check(rej["reason"] == "non_uniform", "reason is non-uniform", rej["reason"])
    # This is the number that separates a dropout from a genuinely irregular
    # record; the coefficient of variation alone cannot tell them apart.
    r.check(rej["n_irregular"] > rej["n_intervals"] * 0.5,
            "most intervals are irregular, unlike a dropout",
            f"{rej['n_irregular']}/{rej['n_intervals']}")


def test_backwards(base, r):
    r.section("a column that goes backwards")
    st, s = open_csv(base, csv_bytes(backwards_times()), "backwards.csv")
    if not r.check(st == 200, "file loads", str(st)):
        return
    rej = s["detected"].get("time_col_rejected")
    if not r.check(rej is not None, "the refusal is reported"):
        return
    r.check(rej["reason"] == "not_monotonic",
            "reported as non-monotonic, not merely uneven", rej["reason"])
    r.check(rej["n_backwards"] == 1, "one backwards step", str(rej["n_backwards"]))


def test_no_time_column_says_nothing(base, r):
    r.section("a file with no time axis")
    # Two plain data channels: nothing here resembles a time vector, so there is
    # no near-miss to explain and the UI should stay quiet.
    rows = ["a,b"] + [f"{(i % 13) * 0.5:.4f},{(i % 7) * 0.25:.4f}" for i in range(N)]
    st, s = open_csv(base, "\n".join(rows).encode(), "notime.csv")
    if not r.check(st == 200, "file loads", str(st)):
        return
    r.check(s["time_col"] == -1, "no time column", str(s["time_col"]))
    r.check(s["detected"].get("time_col_rejected") is None,
            "and nothing is invented to explain")


def test_rejection_survives_reopen(base, r):
    r.section("the explanation is not lost on reopen")
    st, s = open_csv(base, csv_bytes(dropped_sample_times()), "dropout2.csv")
    if not r.check(st == 200, "file loads", str(st)):
        return
    from http_util import get
    st, back = get(base, f"/api/session/{s['session_id']}")
    r.check(st == 200, "session reopens", str(st))
    rej = (back.get("detected") or {}).get("time_col_rejected")
    r.check(rej is not None and rej["reason"] == "non_uniform",
            "a restored session still knows why its rate is manual")


def main(base):
    r = Results()
    print(f"detection tests against {base}")
    test_clean_file_still_detects(base, r)
    test_dropped_sample(base, r)
    test_jitter(base, r)
    test_backwards(base, r)
    test_no_time_column_says_nothing(base, r)
    test_rejection_survives_reopen(base, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
