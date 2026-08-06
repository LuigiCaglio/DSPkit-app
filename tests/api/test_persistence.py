"""Sessions that survive a restart: the disk store, recents, and saved UI state.

Run via `python tests/run_all.py`, which starts a server pointed at a throwaway
DSPKIT_STATE_DIR. To run standalone against an already-running backend:

    python tests/api/test_persistence.py http://127.0.0.1:8000

Note that running it standalone writes into the real ~/.dspkit-app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from http_util import Results, get, post, request_json  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "test_2dof.csv"
EXAMPLE = REPO / "example_data" / "2dof_vibration.csv"


def test_open_by_path(base, r):
    r.section("open by path")
    st, sess = post(base, "/api/session/open", {"path": str(EXAMPLE)})
    if not r.check(st == 200, "a local path can be opened without uploading", str(st)):
        return None
    r.check(sess.get("source_path") == str(EXAMPLE),
            "the response carries the path it was opened from")
    r.check(sess["n_columns"] >= 2, "the file parsed", str(sess["n_columns"]))

    # Reopening the same file must land on the same session, or the settings
    # saved against it would be stranded on an id nothing refers to any more.
    st2, again = post(base, "/api/session/open", {"path": str(EXAMPLE)})
    r.check(st2 == 200, "the same path can be opened again", str(st2))
    r.check(again.get("session_id") == sess["session_id"],
            "reopening a path returns the session it already had")
    r.check(again.get("reopened") is True, "and is flagged as a reopen")
    return sess


def test_missing_path(base, r):
    r.section("paths that don't resolve")
    st, body = post(base, "/api/session/open", {"path": str(REPO / "no_such_file.csv")})
    r.check(st == 404, "a missing path is a 404, not a crash", str(st))
    r.check("no_such_file" in str(body.get("detail", "")),
            "the message names the file it looked for")


def test_cross_site_refused(base, r):
    r.section("filesystem access is same-origin only")
    st, _ = post(base, "/api/session/open", {"path": str(EXAMPLE)},
                 headers={"Origin": "https://example.com"})
    r.check(st == 403, "a cross-site origin cannot read local paths", str(st))

    # The app's own origin, whatever port it happens to be on. Checking against
    # a hardcoded 8000 would pass here while failing for every real launch on
    # any other port -- which is exactly what it did.
    st, _ = post(base, "/api/session/open", {"path": str(EXAMPLE)},
                 headers={"Origin": base})
    r.check(st == 200, "the app's own origin can, on whatever port it runs", str(st))

    # A rebound DNS name resolving to loopback would otherwise agree with its
    # own Origin and sail through the comparison above.
    st, _ = post(base, "/api/session/open", {"path": str(EXAMPLE)},
                 headers={"Origin": "http://evil.example", "Host": "evil.example"})
    r.check(st == 403, "a non-loopback Host is refused even if the Origin matches",
            str(st))


def test_ui_state_roundtrip(base, sess, r):
    r.section("saved UI state")
    sid = sess["session_id"]
    state = {
        "signalCols": [1, 2],
        "focusChannel": 2,
        "timeCol": 0,
        "fsManual": 2048,
        "activeTab": "psd",
        "preproc": {"hpEnabled": True, "hpCutoff": 5},
        "params": {"psd": {"nperseg": 4096}},
    }
    st, _ = request_json(base, f"/api/session/{sid}/state", "PUT", state)
    r.check(st == 200, "UI state can be saved against a session", str(st))

    st, back = get(base, f"/api/session/{sid}")
    r.check(st == 200, "the session can be reopened by id", str(st))
    ui = back.get("ui") or {}
    r.check(ui.get("signalCols") == [1, 2], "channel selection comes back", str(ui.get("signalCols")))
    r.check(ui.get("activeTab") == "psd", "the active tab comes back")
    r.check(ui.get("preproc", {}).get("hpCutoff") == 5, "preprocessing comes back")
    r.check(ui.get("params", {}).get("psd", {}).get("nperseg") == 4096,
            "analysis parameters come back")

    st, _ = request_json(base, f"/api/session/{sid}/state", "PUT", ["not", "an", "object"])
    r.check(st == 422, "a non-object state is rejected", str(st))

    st, _ = request_json(base, "/api/session/nosuchid/state", "PUT", {})
    r.check(st == 404, "saving state for an unknown session is a 404", str(st))


def test_survives_ram_eviction(base, r):
    r.section("sessions outlive the in-memory cache")
    raw = CSV.read_bytes()
    st, first = post(base, "/api/session/create", {}, {"file": (CSV.name, raw)})
    if not r.check(st == 200, "a session to evict", str(st)):
        return
    sid = first["session_id"]

    # _MAX_SESSIONS is 4 parsed arrays; five more uploads push the first out of
    # RAM. Before the disk store this was the point where it became unusable.
    for i in range(5):
        post(base, "/api/session/create", {}, {"file": (f"filler{i}.csv", raw)})

    st, back = get(base, f"/api/session/{sid}")
    r.check(st == 200, "an evicted session is re-read from disk", str(st))
    r.check(back.get("n_samples") == first["n_samples"],
            "and parses to the same thing it did before")

    # And it must still serve analyses, not merely describe itself.
    st, _ = post(base, "/api/spectral/psd", dict(
        session_id=sid, orientation=back["orientation"], header_row=back["header_row"],
        time_col=back["time_col"], fs=back.get("fs") or 1000,
        signal_cols="[1]", signal_col=1, window="hann", nperseg=1024,
        scaling="density",
    ))
    r.check(st == 200, "an evicted session still runs an analysis", str(st))


def test_recent_list(base, r):
    r.section("recent files")
    st, body = get(base, "/api/session/recent")
    if not r.check(st == 200, "recents can be listed", str(st)):
        return
    items = body.get("recent", [])
    r.check(len(items) > 0, "recents is not empty after the tests above",
            f"{len(items)} entries")
    r.check(all("session_id" in it and "filename" in it for it in items),
            "every entry identifies a file")
    r.check(any(it.get("source_path") for it in items),
            "the path-opened file records where it came from")
    r.check(all(it.get("available") for it in items),
            "every entry is still readable")

    times = [it.get("opened_at") or 0 for it in items]
    r.check(times == sorted(times, reverse=True), "newest first")
    r.check(len(items) <= 12, "the list is capped", f"{len(items)} entries")

    # Deleting one must drop it from the list, or the UI offers dead entries.
    victim = items[0]["session_id"]
    request_json(base, f"/api/session/{victim}", "DELETE")
    st, body2 = get(base, "/api/session/recent")
    r.check(victim not in [it["session_id"] for it in body2.get("recent", [])],
            "a deleted session leaves the recent list")


def test_launch_target(base, r):
    r.section("launch target")
    st, body = get(base, "/api/launch-target")
    r.check(st == 200, "the launch target can be asked for", str(st))
    r.check("path" in body, "the response always has a path field")


def main(base):
    r = Results()
    print(f"persistence tests against {base}")
    sess = test_open_by_path(base, r)
    test_missing_path(base, r)
    test_cross_site_refused(base, r)
    if sess:
        test_ui_state_roundtrip(base, sess, r)
    test_survives_ram_eviction(base, r)
    test_recent_list(base, r)
    test_launch_target(base, r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
