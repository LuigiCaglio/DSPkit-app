// Units reaching the actual axes. units.test.mjs covers the algebra; this
// covers the wiring — which chart asks for which unit, and the three cases
// where an axis must stay bare even though a unit is known.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, buildPairOverlay } from '../../frontend/src/lib/plotSpec.js'

// A minimal theme; buildPlot only reads colours off it.
const T = {
  paper: '#fff', bg: '#fff', text: '#000', grid: '#eee', title: '#000',
  legend: '#fff', border: '#ccc', danger: '#f00', warning: '#fa0',
  series: ['#1', '#2', '#3'],
}

const G = { signal: 'g', focus: 'g', x: 'g', y: 'g', byName: { acc1: 'g', acc2: 'g' } }
const opts = (extra = {}) => ({ T, units: G, ...extra })

const yTitle = (spec) => spec.layout.yaxis.title
const xTitle = (spec) => spec.layout.xaxis.title

// ── the amplitude family ─────────────────────────────────────────────────────

const ts = {
  signals: [{ name: 'acc1', signal_raw: [1, 2, 3] }],
  times_raw: [0, 1, 2], preprocessed: false, n_proc: 3, fs_proc: 10,
}

test('a time series axis carries the channel unit', () => {
  assert.equal(yTitle(buildPlot('timeseries', ts, opts())), 'Amplitude [g]')
})

test('an undeclared unit leaves the axis exactly as it was', () => {
  const spec = buildPlot('timeseries', ts, { T, units: {} })
  assert.equal(yTitle(spec), 'Amplitude')
})

test('normalising strips the unit, because the ratio is dimensionless', () => {
  // The regression this guards: 'Amplitude (norm.) [g]', which is false — the
  // series has been divided by its own RMS.
  const spec = buildPlot('timeseries', ts, opts({ normalize: true }))
  assert.equal(yTitle(spec), 'Amplitude (norm.)')
})

test('a mixed selection silences the shared axis', () => {
  const mixed = { signal: '', focus: 'g', byName: { acc1: 'g', disp: 'mm' } }
  assert.equal(yTitle(buildPlot('timeseries', ts, { T, units: mixed })), 'Amplitude')
})

test('but a small-multiples cell recovers its own channel unit', () => {
  // Each cell shows one channel, so mixed units do not make *this* cell unknown.
  const mixed = { signal: '', focus: '', byName: { acc1: 'g', disp: 'mm' } }
  const spec = buildPlot('timeseries', ts, { T, units: mixed, cell: true, title: 'acc1' })
  assert.equal(yTitle(spec), 'Amplitude [g]')
})

// ── the derived ones ─────────────────────────────────────────────────────────

test('a PSD axis is squared and per-hertz, not the bare channel unit', () => {
  const d = { freqs: [1, 2], signals: [{ name: 'acc1', Pxx: [1, 2] }] }
  assert.equal(yTitle(buildPlot('psd', d, opts())), 'PSD [g²/Hz]')
})

test('a compound channel unit is bracketed on the PSD axis', () => {
  const d = { freqs: [1, 2], signals: [{ name: 'acc1', Pxx: [1, 2] }] }
  const u = { signal: 'm/s²', byName: {} }
  assert.equal(yTitle(buildPlot('psd', d, { T, units: u })), 'PSD [(m/s²)²/Hz]')
})

test('a cross-spectrum uses both channels, not the selection', () => {
  const d = { freqs: [1, 2], magnitude: [1, 2], phase_deg: [0, 0] }
  const u = { signal: '', x: 'N', y: 'mm', byName: {} }
  assert.equal(yTitle(buildPlot('csd', d, { T, units: u })), '|CSD| [N·mm/Hz]')
})

test('a probability density gets the reciprocal on y and the unit on x', () => {
  const d = { signals: [{ name: 'acc1', xi: [1], density: [1], bin_centres: [1], hist_density: [1] }] }
  const u = { focus: 'm/s²', byName: {} }
  const spec = buildPlot('statistics', d, { T, units: u })
  assert.equal(xTitle(spec), 'Value [m/s²]')
  assert.equal(yTitle(spec), 'Density [1/(m/s²)]')
})

test('several channels overlay, each keeping one hue for both its marks', () => {
  const mk = (name) => ({ name, xi: [1], density: [1], bin_centres: [1], hist_density: [1] })
  const d = { signals: [mk('a'), mk('b')] }
  const spec = buildPlot('statistics', d, { T, units: { byName: {} } })
  // two channels x (histogram + KDE)
  assert.equal(spec.traces.length, 4)
  const hist = spec.traces.filter(t => t.type === 'bar')
  const kde  = spec.traces.filter(t => t.type !== 'bar')
  assert.equal(hist.length, 2)
  assert.equal(kde.length, 2)
  assert.equal(hist[0].marker.color, kde[0].line.color)
})

test('the histogram and the KDE can each be turned off', () => {
  const d = { signals: [{ name: 'a', xi: [1], density: [1], bin_centres: [1], hist_density: [1] }] }
  const o = { T, units: { byName: {} } }
  assert.equal(buildPlot('statistics', d, { ...o, showHist: false }).traces.length, 1)
  assert.equal(buildPlot('statistics', d, { ...o, showKde: false }).traces.length, 1)
  assert.equal(buildPlot('statistics', d, { ...o, showHist: false, showKde: false }).traces.length, 0)
})

// ── the payload deciding the unit ────────────────────────────────────────────

test('a normalized ACF stays dimensionless', () => {
  const d = { lags: [0, 1], signals: [{ name: 'acc1', acf: [1, 0] }], normalized: true }
  assert.equal(yTitle(buildPlot('autocorrelation', d, opts())), 'ACF')
})

test('an unnormalized ACF is in the unit squared', () => {
  const d = { lags: [0, 1], signals: [{ name: 'acc1', acf: [1, 0] }], normalized: false }
  assert.equal(yTitle(buildPlot('autocorrelation', d, opts())), 'ACF [g²]')
})

test('an old payload with no normalized flag is treated as normalized', () => {
  // Absent means "the backend that produced this predates the flag"; its
  // default was normalize=true, so the dimensionless label is the right guess.
  const d = { lags: [0, 1], signals: [{ name: 'acc1', acf: [1, 0] }] }
  assert.equal(yTitle(buildPlot('autocorrelation', d, opts())), 'ACF')
})

// ── the single-channel analyses ──────────────────────────────────────────────

test('the focus channel unit reaches the one-channel charts', () => {
  const u = { signal: '', focus: 'kN', byName: {} }   // mixed selection, known focus
  const f = { times: [0, 1], signal_raw: [1, 2], signal_filtered: [1, 2] }
  assert.equal(yTitle(buildPlot('filter', f, { T, units: u })), 'Amplitude [kN]')

  const e = { times: [0, 1], imfs: [[1, 2]], residue: [0, 0] }
  assert.equal(yTitle(buildPlot('emd', e, { T, units: u })), 'Amplitude [kN]')
})

// ── heatmap colourbars ───────────────────────────────────────────────────────

const surface = { times: [0, 1], freqs: [1, 2], magnitude: [[1, 2], [3, 4]] }
const cbar = (spec) => spec.traces[0].colorbar.title.text

test('a linear STFT colourbar carries the signal unit', () => {
  const spec = buildPlot('stft', surface, opts({ tf: { db: false } }))
  assert.equal(cbar(spec), 'magnitude [g]')
})

test('dB mode is relative to peak, so no unit appears', () => {
  const spec = buildPlot('stft', surface, opts({ tf: { db: true } }))
  assert.equal(cbar(spec), 'dB re peak')
})

test('WVD stays bare — its energy-density scaling makes the unit ambiguous', () => {
  const w = { times: [0, 1], freqs: [1, 2], wvd: [[1, 2], [3, 4]] }
  const spec = buildPlot('wvd', w, opts({ tf: { db: false } }))
  assert.equal(cbar(spec), 'magnitude')
})

// ── overlays, where several channels share one axis ──────────────────────────

const ccfItem = (name) => ({ name, data: { lags: [-1, 0, 1], ccf: [0, 1, 0], normalized: false } })

test('an overlay of channels that agree carries the unit', () => {
  const spec = buildPairOverlay('cross_correlation', [ccfItem('acc1'), ccfItem('acc2')],
    { T, ref: 'acc1', units: G })
  assert.equal(yTitle(spec), 'CCF [g²]')
})

test('one disagreeing channel silences the whole overlay axis', () => {
  const u = { byName: { acc1: 'g', acc2: 'g', disp: 'mm' } }
  const spec = buildPairOverlay('cross_correlation',
    [ccfItem('acc1'), ccfItem('acc2'), ccfItem('disp')],
    { T, ref: 'acc1', units: u })
  assert.equal(yTitle(spec), 'CCF')
})

test('a normalized overlay is dimensionless whatever the channels are', () => {
  const items = [{ name: 'acc1', data: { lags: [0], ccf: [1], normalized: true } }]
  const spec = buildPairOverlay('cross_correlation', items, { T, ref: 'acc1', units: G })
  assert.equal(yTitle(spec), 'CCF')
})

test('charts called with no units at all still build', () => {
  // Every call site passing units is new; none of them may become required.
  for (const [tab, d] of [
    ['timeseries', ts],
    ['psd', { freqs: [1], signals: [{ name: 'a', Pxx: [1] }] }],
    ['fft', { freqs: [1], signals: [{ name: 'a', amplitude: [1], phase: [0] }] }],
    ['coherence', { freqs: [1], Cxy: [1] }],
  ]) {
    const spec = buildPlot(tab, d, { T })
    assert.ok(spec && spec.layout, `${tab} should still build without units`)
  }
})

// ── cross-correlation lead direction ─────────────────────────────────────────
// dspkit's own docstring stated this backwards until 2026-09-02, so the claim
// the chart makes is pinned here rather than left to be re-derived.

test('a positive peak lag says the X channel leads', () => {
  const d = {
    lags: [-1, 0, 1], ccf: [0.1, 0.2, 0.9],
    x_label: 'acc1', y_label: 'acc2', normalized: true,
  }
  const spec = buildPlot('cross_correlation', d, { T, units: { byName: {} } })
  assert.match(spec.layout.title.text, /acc1 leads acc2/)
})

test('a negative peak lag says the Y channel leads', () => {
  const d = {
    lags: [-1, 0, 1], ccf: [0.9, 0.2, 0.1],
    x_label: 'acc1', y_label: 'acc2', normalized: true,
  }
  const spec = buildPlot('cross_correlation', d, { T, units: { byName: {} } })
  assert.match(spec.layout.title.text, /acc2 leads acc1/)
})

test('a peak at zero lag claims no lead in either direction', () => {
  const d = {
    lags: [-1, 0, 1], ccf: [0.1, 0.9, 0.1],
    x_label: 'acc1', y_label: 'acc2', normalized: true,
  }
  const spec = buildPlot('cross_correlation', d, { T, units: { byName: {} } })
  assert.match(spec.layout.title.text, /in phase, no lead/)
})
