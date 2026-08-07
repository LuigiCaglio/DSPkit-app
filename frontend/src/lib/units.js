// Physical units for channels, and the algebra that carries them onto an axis.
//
// A unit is declared per channel and is purely a display concern — nothing here
// converts or scales anything, because the numbers in the file are already in
// whatever the user says they are in. What this module does is answer "given
// that channel 3 is in m/s², what does the PSD axis say?", which is the part
// that is easy to get wrong by hand: an acceleration PSD is (m/s²)²/Hz, not
// m/s²/Hz, and a density is 1/(m/s²).
//
// The rule throughout: a unit is only shown when it is *known and unambiguous*.
// Two channels in different units share one axis on every overlay plot, so the
// label falls back to the bare quantity rather than claiming the first channel's
// unit applies to all of them. Silence is correct; a wrong unit is not.
//
// Deliberately free of Svelte runes so the tests can import it under plain node,
// the same arrangement plotSpec.js and sessionState.js use.

/** Offered in the picker; any other string is still accepted. */
export const UNIT_PRESETS = [
  'm/s²', 'g', 'mm/s', 'm/s', 'mm', 'm', 'µm',
  'N', 'kN', 'Nm', 'Pa', 'kPa', 'MPa',
  'µε', 'V', 'mV', '°C', '%',
]

/** Longest unit string kept; anything past this is a paste accident. */
const MAX_UNIT_LEN = 16

/**
 * Clean a user-typed unit into what gets stored.
 *
 * Returns '' for anything blank, which is the "not declared" state — callers
 * treat '' and undefined identically so an un-declared channel and a channel
 * whose unit was cleared behave the same.
 */
export function normalizeUnit(raw) {
  if (typeof raw !== 'string') return ''
  // Commas, quotes and newlines are stripped rather than escaped: a unit
  // travels into CSV headers, where any of them would split or break a column,
  // and none of them mean anything in a unit anyway.
  return raw.replace(/[",\r\n]/g, '').trim().slice(0, MAX_UNIT_LEN)
}

/** A unit needs bracketing before it can take an exponent. */
function isCompound(u) {
  return /[/·*^\s()]/.test(u)
}

/** `m/s²` → `(m/s²)`, `g` → `g` — only when an exponent is about to be applied. */
function group(u) {
  return isCompound(u) ? `(${u})` : u
}

/**
 * The unit squared: `m/s²` → `(m/s²)²`, `g` → `g²`.
 *
 * The bracketing is what makes this worth a function. `m/s²²` is meaningless
 * and `m²/s⁴` — while correct — is not how anyone writes an acceleration PSD.
 */
export function squared(unit) {
  const u = normalizeUnit(unit)
  return u ? `${group(u)}²` : ''
}

/** The product of two channels' units, as a cross-spectrum needs. */
export function product(a, b) {
  const ua = normalizeUnit(a), ub = normalizeUnit(b)
  if (!ua || !ub) return ''
  return ua === ub ? squared(ua) : `${ua}·${ub}`
}

/** Per-hertz, as any spectral *density* is: `(m/s²)²` → `(m/s²)²/Hz`. */
export function perHz(unit) {
  const u = normalizeUnit(unit)
  return u ? `${u}/Hz` : ''
}

/** A power spectral density's unit: `m/s²` → `(m/s²)²/Hz`. */
export function psdUnit(unit) {
  return perHz(squared(unit))
}

/** A cross-spectral density's unit, from the two channels it relates. */
export function csdUnit(a, b) {
  return perHz(product(a, b))
}

/**
 * A probability density's unit — the reciprocal of the variable's.
 *
 * A PDF integrates to 1 over the variable, so its height is per-unit-of-x. This
 * is the axis people most often leave bare, and the one where bare is most
 * misleading: the *number* changes if you switch mm to m.
 */
export function densityUnit(unit) {
  const u = normalizeUnit(unit)
  return u ? `1/${group(u)}` : ''
}

/**
 * Attach a unit to an axis label: `('Amplitude', 'g')` → `'Amplitude [g]'`.
 *
 * An unknown unit leaves the label exactly as it was, so every call site can
 * pass a possibly-empty unit without guarding.
 */
export function withUnit(label, unit) {
  const u = normalizeUnit(unit)
  return u ? `${label} [${u}]` : label
}

/**
 * The unit shared by every one of `cols`, or '' if they disagree.
 *
 * `units` is keyed by column index. A single channel with no declared unit is
 * indistinguishable from a mix, and both correctly produce '' — there is no
 * unit that can honestly be printed in either case.
 */
export function commonUnit(units, cols) {
  if (!units || !Array.isArray(cols) || cols.length === 0) return ''
  const first = normalizeUnit(units[cols[0]])
  if (!first) return ''
  for (const c of cols) if (normalizeUnit(units[c]) !== first) return ''
  return first
}

/**
 * Resolve everything the chart builders need, once, from the current selection.
 *
 * Charts are handed resolved strings rather than the map plus indices, so that
 * `plotSpec` never has to know what a column index is.
 *
 * `signal` is for the charts that overlay the whole selection; `focus` is for
 * the ones that run on a single channel (filtering, EMD, the distributions).
 * They are different questions — a mixed selection silences `signal` while
 * `focus` stays perfectly well known.
 *
 * @param units       {[col]: unit} as stored on the session
 * @param sel         the selected channel indices
 * @param pair        {x, y} for the two-channel analyses
 * @param names       column names, for the per-channel grid cells
 * @param focusCol    the single channel the one-channel analyses run on
 * @returns {{signal, focus, x, y, byName}}
 */
export function resolveUnits(units, sel = [], pair = {}, names = [], focusCol = null) {
  const byName = {}
  if (units && Array.isArray(names)) {
    names.forEach((n, i) => {
      const u = normalizeUnit(units[i])
      if (u) byName[n] = u
    })
  }
  return {
    signal: commonUnit(units, sel),
    focus: normalizeUnit(units?.[focusCol]),
    x: normalizeUnit(units?.[pair.x]),
    y: normalizeUnit(units?.[pair.y]),
    byName,
  }
}

/**
 * The unit common to a set of channel *names*, or '' if they disagree.
 *
 * The overlay builders receive names rather than indices — they are handed
 * per-channel payloads, not the selection — so the same honesty rule needs a
 * name-keyed entry point.
 */
export function commonUnitByName(byName, names) {
  if (!byName || !Array.isArray(names) || names.length === 0) return ''
  const first = normalizeUnit(byName[names[0]])
  if (!first) return ''
  for (const n of names) if (normalizeUnit(byName[n]) !== first) return ''
  return first
}

/**
 * Drop entries that no longer name a column in this file.
 *
 * The same distrust `applyState` applies to a restored channel selection: a
 * session's file can be re-read with a different layout or edited on disk, and
 * a unit stranded on column 7 of a 3-column file would otherwise sit in the
 * blob forever.
 */
export function sanitizeUnits(raw, nColumns) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  if (!Number.isInteger(nColumns) || nColumns <= 0) return {}
  const out = {}
  for (const [k, v] of Object.entries(raw)) {
    const i = Number(k)
    if (!Number.isInteger(i) || i < 0 || i >= nColumns) continue
    const u = normalizeUnit(v)
    if (u) out[i] = u
  }
  return out
}
