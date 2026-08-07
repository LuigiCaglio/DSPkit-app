// The Time-Frequency Explorer's logic, separate from its chart.
//
// The coverage was never the weak part — STFT, CWT, WVD and SPWVD all work.
// What was missing is *comparison*: they lived in four tabs with independent
// colour scales, so the question you actually have ("which of these is telling
// me the truth about this signal?") could not be asked. One surface, one scale,
// one selector is the whole idea.
//
// Two things here are worth reading before changing anything: the slices, which
// are taken from the matrix already in memory rather than by asking the backend
// again, and the length cap, which is what stops WVD from hanging the app.
//
// Free of Svelte runes so the tests can import it under plain node.

/** Index of the entry closest to `v`, for an ascending array. */
export function nearestIndex(arr, v) {
  if (!arr || arr.length === 0) return -1
  let lo = 0, hi = arr.length - 1
  if (v <= arr[lo]) return lo
  if (v >= arr[hi]) return hi
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (arr[mid] === v) return mid
    if (arr[mid] < v) lo = mid; else hi = mid
  }
  return (v - arr[lo] <= arr[hi] - v) ? lo : hi
}

/**
 * The spectrum at one instant: a column of the surface.
 *
 * `z` is indexed [frequency][time], which is what every one of the timefreq
 * endpoints returns and what Plotly's heatmap expects. Taking a column is
 * therefore the awkward direction, and getting it backwards silently produces a
 * plausible-looking curve of the wrong length — hence the explicit tests.
 */
export function spectrumAt(z, timeIndex) {
  if (!Array.isArray(z) || z.length === 0) return []
  if (timeIndex < 0 || timeIndex >= (z[0]?.length ?? 0)) return []
  return z.map(row => row[timeIndex])
}

/** How one frequency's energy evolves: a row of the surface. */
export function envelopeAt(z, freqIndex) {
  if (!Array.isArray(z) || freqIndex < 0 || freqIndex >= z.length) return []
  return [...z[freqIndex]]
}

/**
 * The resolution the chosen window actually bought, measured off the returned
 * axes rather than re-derived from the parameters.
 *
 * Deriving Δf as fs/nperseg would be a second implementation of what the
 * backend already did, and would quietly disagree with it for CWT — whose
 * frequency axis is geometric, not uniform. Measuring the axis cannot disagree
 * with the axis.
 */
export function resolution(times, freqs) {
  const span = (a) => (Array.isArray(a) && a.length > 1)
    ? (a[a.length - 1] - a[0]) / (a.length - 1)
    : null
  const dt = span(times)
  const df = span(freqs)
  // A geometric frequency axis has no single Δf; saying "0.5 Hz" for a CWT
  // whose bins run 1, 1.1, 1.2 … 400 would be a made-up number.
  const uniform = isUniform(freqs)
  return { dt, df: uniform ? df : null, uniformFreq: uniform }
}

/** True when the spacing is constant to within a part in a thousand. */
export function isUniform(a) {
  if (!Array.isArray(a) || a.length < 3) return true
  const first = a[1] - a[0]
  if (!(Math.abs(first) > 0)) return false
  for (let i = 2; i < a.length; i++) {
    const d = a[i] - a[i - 1]
    if (Math.abs(d - first) > Math.abs(first) * 1e-3) return false
  }
  return true
}

const sig = (v, n = 3) => {
  if (v == null || !Number.isFinite(v)) return null
  return Number(v.toPrecision(n))
}

/**
 * The resolution as a sentence, because `nperseg = 1024` is not an answer to
 * "can this separate two modes 0.4 Hz apart?".
 */
export function describeResolution(times, freqs) {
  const { dt, df, uniformFreq } = resolution(times, freqs)
  if (dt == null) return ''
  const parts = [`Δt ${sig(dt)} s`]
  if (uniformFreq && df != null) parts.push(`Δf ${sig(df)} Hz`)
  else parts.push('Δf varies (geometric axis)')
  return parts.join('  ·  ')
}

// ── cost control ─────────────────────────────────────────────────────────────

/**
 * Transforms whose cost grows faster than linearly in the record length.
 *
 * WVD forms an N×N outer product before transforming it, so a 20 000-sample
 * record is not 20x a 1 000-sample one — it is 400x, and it is what the browser
 * waits on. SPWVD smooths the same construction and pays the same price.
 */
export const EXPENSIVE = new Set(['wvd', 'spwvd'])

/**
 * Longest record fed to an O(N²) transform from the Explorer.
 *
 * 2048 is not a new number: it is the limit the WVD tab has always warned
 * about ("Signal must be ≤ 2048 samples"). The difference is that the Explorer
 * *enforces* it rather than leaving it to you, because its premise is that you
 * flip between transforms on the same data and compare — which is only true if
 * flipping is fast. The standalone WVD tab is unchanged and still takes
 * whatever you give it; this cap is the price of the surface being
 * interactive, and it is stated on screen rather than applied quietly.
 */
export const EXPLORER_MAX_SAMPLES = 2048

/**
 * What to send, and what to say about it.
 *
 * Returns the sample window the Explorer should ask for. A capped run is
 * *centred* on the record rather than taken from the front: the start of a
 * measurement is usually settling, and the middle is where the event is.
 */
export function costPlan(transform, nSamples, fs) {
  const expensive = EXPENSIVE.has(transform)
  if (!expensive || !Number.isFinite(nSamples) || nSamples <= EXPLORER_MAX_SAMPLES) {
    return { capped: false, start: 0, count: nSamples, notice: '' }
  }
  const count = EXPLORER_MAX_SAMPLES
  const start = Math.floor((nSamples - count) / 2)
  const secs = Number.isFinite(fs) && fs > 0 ? ` (${sig(count / fs)} s)` : ''
  return {
    capped: true,
    start,
    count,
    notice: `${transform.toUpperCase()} is O(N²), so the Explorer runs it on ` +
            `${count.toLocaleString()} samples${secs} from the middle of the ` +
            `record instead of all ${nSamples.toLocaleString()}. ` +
            `The ${transform.toUpperCase()} tab runs the full record.`,
  }
}

/**
 * The surface size the Explorer asks the backend for.
 *
 * The cap on input samples fixes compute time; this fixes the *payload*, which
 * is the other half of the same problem and the one that actually froze the
 * browser. A capped 2048-sample WVD is still 1025 x 2048 values — about 48 MB
 * of JSON, for a panel a few hundred pixels tall. These numbers are chosen
 * against the screen, not the signal: more cells than pixels cannot be seen.
 *
 * The backend keeps the largest-magnitude value in each block rather than
 * striding, so a one-bin ridge survives being thinned.
 */
export const SURFACE_MAX_FREQ = 400
export const SURFACE_MAX_TIME = 600

/** The decimation fields to send with any Explorer transform request. */
export function surfaceLimits() {
  return { max_freq: SURFACE_MAX_FREQ, max_time: SURFACE_MAX_TIME }
}

/** The transforms the Explorer can switch between, in increasing cost order. */
export const TRANSFORMS = [
  { id: 'stft',  label: 'STFT',  endpoint: '/api/timefreq/stft',  field: 'magnitude' },
  { id: 'cwt',   label: 'CWT',   endpoint: '/api/timefreq/cwt',   field: 'magnitude' },
  { id: 'wvd',   label: 'WVD',   endpoint: '/api/timefreq/wvd',   field: 'wvd' },
  { id: 'spwvd', label: 'SPWVD', endpoint: '/api/timefreq/spwvd', field: 'spwvd' },
]

export const transformById = (id) => TRANSFORMS.find(t => t.id === id) ?? TRANSFORMS[0]

/** The surface out of a payload, whichever key that transform used for it. */
export function surfaceOf(transform, payload) {
  if (!payload) return null
  return payload[transformById(transform).field] ?? null
}
