# Tests

No third-party packages required — the API suite drives a real server over
`urllib`, and the frontend suite uses node's built-in test runner.

```
python tests/run_all.py
```

That starts a backend on a free port, runs the API tests against it, tears it
down, then runs `node --test tests/frontend`. Non-zero exit if anything fails.

To run one suite on its own:

```
python tests/api/test_api.py http://127.0.0.1:8000    # against a running backend
node --test tests/frontend
```

## What's covered

**`api/test_api.py`** — behaviour against the committed `test_2dof.csv`:
auto-detection (header, time column, derived `fs`), the three calls Overview
composes, the single-channel fan-out, session errors, and the rule that one
selected channel reaches everything except the four genuinely between-sensor
analyses.

It also pins the FDD result that motivated the output-only warning in the UI:
the two response channels give the true 10 and 25 Hz modes, and including the
force columns loses them.

**`frontend/*.test.mjs`** — `frontend/src/lib/plotSpec.js` is deliberately free
of Svelte runes, so node imports it directly and the chart definitions are
testable without a browser. Covers display-window downsampling, cross-correlation
lag handling and overlays, and the filter-band shading and picking mode.

## Not covered

Anything requiring a rendered DOM: drag-resizing, the scroll behaviour of the
plot area, parameter persistence across tab switches, and whether auto-run fires
on mount. See the "Known-unverified" section of `TODO.md` — including the
headless-Edge approach used to check CSS layout when a browser is unavailable.
