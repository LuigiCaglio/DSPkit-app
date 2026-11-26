# Keeping Python and Rust in sync

This app has a native twin: `dspkit-gui.exe`, built from `../dspkit-rs`
(`src/gui/` answers the same `/api` contract as `backend/main.py`, and embeds
this frontend). **A change here is not done until the exe has it too.**

- `backend/main.py` (endpoints, file loading, preprocessing, responses,
  messages) -> the same in `../dspkit-rs/src/gui/` (`api.rs`, file reading in
  `table.rs`, `.mat` in `matfile.rs`). Add a case to
  `../dspkit-rs/tools/gui_parity.py`; it runs both backends side by side and
  must pass.
- `frontend/src/` -> rebuild both bundles: `../dspkit-rs/tools/sync_frontend.sh`
  builds into `dspkit-rs/frontend_dist/`; copy that into `frontend/dist/`
  (remove the old asset) so both ship the same page.
- Run `python tests/run_all.py` here as well.

Full guide, with what-to-change-where and every check:
`../dspkit-rs/KEEPING_IN_SYNC.md`.
