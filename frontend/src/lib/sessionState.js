// What "where you left off" means, as plain data.
//
// The app used to keep everything in component state, so a reload — let alone a
// restart — threw away the channel selection, the preprocessing chain and every
// analysis parameter. This module defines the blob that gets saved against a
// session and, more importantly, the rules for reading one back safely.
//
// Deliberately free of Svelte runes so the tests can import it under plain node,
// the same arrangement plotSpec.js uses.

import { ALL_CHANNELS } from './analyses.js'
import { sanitizeUnits } from './units.js'

/**
 * Bumped when a change would make an old blob mean something different.
 *
 * Adding `units` did *not* bump it: an old blob simply has no units, which is
 * exactly the "not declared yet" state. Bumping would have discarded every
 * saved channel selection and filter to add an optional field.
 */
export const STATE_VERSION = 1

/** The preprocessing chain in its off position — one definition, shared. */
export function defaultPreproc() {
  return {
    windowEnabled:   false,
    winUnit:         'samples',
    winStart:        null,
    winEnd:          null,
    detrendEnabled:  false,
    detrendOrder:    0,
    hpEnabled:       false,
    hpCutoff:        10,
    hpOrder:         4,
    lpEnabled:       false,
    lpCutoff:        500,
    lpOrder:         4,
    notchEnabled:    false,
    notchFreq:       50,      // mains hum in Europe
    notchQ:          30,
    zeroPhase:       true,    // offline analysis: no phase distortion
    calculusEnabled: false,
    calculusOrder:   -1,        // -1/-2 integrate, +1/+2 differentiate
    calculusHp:      0.5,
    calculusLp:      null,
    calculusTaper:   0,        // fraction of the record tapered at each end
    resampleEnabled: false,
    targetFs:        512,
  }
}

/** Collect the current UI into the blob that gets stored. */
export function buildState(ui) {
  return {
    version:        STATE_VERSION,
    orientation:    ui.orientation,
    headerRow:      ui.headerRow,
    timeCol:        ui.timeCol,
    fsManual:       ui.fsManual,
    signalCols:     [...(ui.signalCols ?? [])],
    units:          { ...(ui.units ?? {}) },
    focusChannel:   ui.focusChannel,
    pairX:          ui.pairX,
    pairY:          ui.pairY,
    preproc:        { ...(ui.preproc ?? {}) },
    activeCategory: ui.activeCategory,
    activeTab:      ui.activeTab,
    params:         ui.params ?? {},
  }
}

const isInt = (v) => Number.isInteger(v)

/**
 * Read a stored blob back, clamped to what this file can actually support.
 *
 * A saved selection is not trustworthy on arrival: the file behind a session can
 * be re-read with a different layout, or edited on disk to have fewer columns.
 * Restoring `signalCols: [4]` onto a 2-column file would leave every analysis
 * failing with an out-of-range error and no clue why, so out-of-range channels
 * are dropped here and the caller falls back to its own defaults if nothing
 * usable survives.
 *
 * Returns null when there is nothing worth restoring, so callers can treat
 * "no saved state" and "unusable saved state" the same way.
 */
export function applyState(raw, { nColumns, timeCol = -1 } = {}) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  if (raw.version !== STATE_VERSION) return null
  if (!isInt(nColumns) || nColumns <= 0) return null

  const inRange = (i) => isInt(i) && i >= 0 && i < nColumns

  const cols = Array.isArray(raw.signalCols) ? raw.signalCols.filter(inRange) : []
  // The time column is an axis, not a signal — never restore it as one.
  const signalCols = [...new Set(cols)].filter((i) => i !== timeCol).sort((a, b) => a - b)
  if (signalCols.length === 0) return null

  const pick = (v, fallback) => (signalCols.includes(v) ? v : fallback)
  const focus = raw.focusChannel === ALL_CHANNELS
    ? ALL_CHANNELS
    : pick(raw.focusChannel, signalCols[0])

  const state = {
    signalCols,
    // Keyed by column index like everything else here, and clamped the same way
    // — a unit stranded on column 7 of a 3-column file is dropped rather than
    // kept forever. Note this rides along with the rest: if the selection no
    // longer fits and this function returns null, the units go too, because a
    // half-restored state is harder to reason about than a fresh one.
    units: sanitizeUnits(raw.units, nColumns),
    focusChannel: focus,
    pairX: pick(raw.pairX, signalCols[0]),
    pairY: pick(raw.pairY, signalCols[1] ?? signalCols[0]),
    preproc: { ...defaultPreproc(), ...(raw.preproc ?? {}) },
    params: (raw.params && typeof raw.params === 'object' && !Array.isArray(raw.params))
      ? raw.params
      : {},
  }
  if (typeof raw.activeCategory === 'string') state.activeCategory = raw.activeCategory
  if (typeof raw.activeTab === 'string') state.activeTab = raw.activeTab
  if (Number.isFinite(raw.fsManual) && raw.fsManual > 0) state.fsManual = raw.fsManual
  return state
}

/**
 * Coalesce saves.
 *
 * Every keystroke in a cutoff box changes the state; writing each one would put
 * a file write behind every character typed. The trailing edge is the one that
 * matters — the value the user stopped on.
 */
export function debounce(fn, ms = 600) {
  let timer = null
  const wrapped = (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { timer = null; fn(...args) }, ms)
  }
  wrapped.cancel = () => { if (timer) { clearTimeout(timer); timer = null } }
  wrapped.flush = (...args) => { wrapped.cancel(); fn(...args) }
  return wrapped
}

/** Human-readable "opened 3 minutes ago", for the recent-files list. */
export function relativeTime(epochSeconds, now = Date.now() / 1000) {
  if (!Number.isFinite(epochSeconds)) return ''
  const s = Math.max(0, now - epochSeconds)
  if (s < 60) return 'just now'
  const mins = Math.round(s / 60)
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} d ago`
  return new Date(epochSeconds * 1000).toLocaleDateString()
}

/**
 * Shorten a path for display, keeping the end.
 *
 * The tail is what distinguishes two recordings; the leading directories are
 * usually the same for all of them.
 */
export function shortPath(path, maxLen = 44) {
  if (!path) return ''
  const norm = path.replace(/\\/g, '/')
  if (norm.length <= maxLen) return path
  const parts = norm.split('/')
  let out = parts[parts.length - 1]
  for (let i = parts.length - 2; i >= 0; i--) {
    const next = `${parts[i]}/${out}`
    if (next.length + 1 > maxLen) break
    out = next
  }
  return `…/${out}`
}
