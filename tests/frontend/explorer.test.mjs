// The Explorer's two load-bearing pieces: slices taken out of the surface
// already in memory, and the cost cap that stops WVD hanging the browser.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  nearestIndex, spectrumAt, envelopeAt, resolution, isUniform,
  describeResolution, costPlan, surfaceOf, transformById,
  EXPENSIVE, EXPLORER_MAX_SAMPLES, TRANSFORMS,
} from '../../frontend/src/lib/explorer.js'
import { buildExplorer } from '../../frontend/src/lib/plotSpec.js'

// ── finding the cursor ───────────────────────────────────────────────────────

const axis = [0, 1, 2, 3, 4]

test('a click lands on the nearest sample, not the one before it', () => {
  assert.equal(nearestIndex(axis, 2.4), 2)
  assert.equal(nearestIndex(axis, 2.6), 3)
  assert.equal(nearestIndex(axis, 2.5), 2)   // ties go low, deterministically
})

test('a click outside the axis clamps to its ends', () => {
  assert.equal(nearestIndex(axis, -10), 0)
  assert.equal(nearestIndex(axis, 99), 4)
})

test('an empty axis has no nearest index', () => {
  assert.equal(nearestIndex([], 1), -1)
  assert.equal(nearestIndex(null, 1), -1)
})

// ── slicing the surface ──────────────────────────────────────────────────────

// z is [frequency][time]: 3 frequencies, 4 time steps.
const z = [
  [1, 2, 3, 4],
  [5, 6, 7, 8],
  [9, 10, 11, 12],
]

test('a spectrum is a column — one value per frequency', () => {
  // Getting this axis backwards yields a plausible curve of the wrong length,
  // which is exactly the bug that would not be noticed by eye.
  assert.deepEqual(spectrumAt(z, 0), [1, 5, 9])
  assert.deepEqual(spectrumAt(z, 3), [4, 8, 12])
  assert.equal(spectrumAt(z, 1).length, z.length)
})

test('an envelope is a row — one value per time step', () => {
  assert.deepEqual(envelopeAt(z, 0), [1, 2, 3, 4])
  assert.deepEqual(envelopeAt(z, 2), [9, 10, 11, 12])
  assert.equal(envelopeAt(z, 1).length, z[0].length)
})

test('an out-of-range slice is empty rather than undefined-filled', () => {
  assert.deepEqual(spectrumAt(z, 9), [])
  assert.deepEqual(spectrumAt(z, -1), [])
  assert.deepEqual(envelopeAt(z, 9), [])
  assert.deepEqual(envelopeAt([], 0), [])
})

test('an envelope is a copy, so mutating it cannot corrupt the surface', () => {
  const e = envelopeAt(z, 0)
  e[0] = 999
  assert.equal(z[0][0], 1)
})

// ── resolution, measured rather than re-derived ──────────────────────────────

test('a uniform axis reports both resolutions', () => {
  const r = resolution([0, 0.5, 1.0, 1.5], [0, 2, 4, 6])
  assert.equal(r.dt, 0.5)
  assert.equal(r.df, 2)
  assert.equal(r.uniformFreq, true)
})

test('a geometric frequency axis reports no single Δf', () => {
  // A CWT's frequency axis is geometric. Quoting one Δf for it would be a made
  // -up number, so the readout says the axis varies instead.
  const geo = [1, 2, 4, 8, 16, 32]
  assert.equal(isUniform(geo), false)
  const r = resolution([0, 1, 2], geo)
  assert.equal(r.df, null)
  assert.equal(r.uniformFreq, false)
  assert.match(describeResolution([0, 1, 2], geo), /varies/)
})

test('the readout is a sentence with units, not a parameter dump', () => {
  const s = describeResolution([0, 0.5, 1.0], [0, 2, 4])
  assert.match(s, /Δt 0\.5 s/)
  assert.match(s, /Δf 2 Hz/)
})

test('an axis too short to have a spacing yields nothing', () => {
  assert.equal(describeResolution([0], [0]), '')
  assert.equal(resolution([], []).dt, null)
})

// ── the cost cap ─────────────────────────────────────────────────────────────

test('cheap transforms are never capped, however long the record', () => {
  for (const t of ['stft', 'cwt']) {
    const p = costPlan(t, 1_000_000, 1024)
    assert.equal(p.capped, false)
    assert.equal(p.count, 1_000_000)
    assert.equal(p.notice, '')
  }
})

test('WVD and SPWVD are the expensive ones', () => {
  assert.ok(EXPENSIVE.has('wvd') && EXPENSIVE.has('spwvd'))
  assert.ok(!EXPENSIVE.has('stft') && !EXPENSIVE.has('cwt'))
})

test('a long record is capped for WVD, and says so', () => {
  const p = costPlan('wvd', 20480, 1024)
  assert.equal(p.capped, true)
  assert.equal(p.count, EXPLORER_MAX_SAMPLES)
  assert.match(p.notice, /O\(N²\)/)
  // Built with toLocaleString, as the rest of the app is, so the separator is
  // the reader's — assert against the same call rather than a hardcoded comma.
  assert.ok(p.notice.includes((20480).toLocaleString()), 'says what it did not use')
  assert.ok(p.notice.includes(EXPLORER_MAX_SAMPLES.toLocaleString()), 'and what it did')
  assert.match(p.notice, /WVD tab/)         // and where the full record lives
})

test('the capped window is centred, since records start with settling', () => {
  const p = costPlan('wvd', 20480, 1024)
  assert.equal(p.start, Math.floor((20480 - EXPLORER_MAX_SAMPLES) / 2))
  assert.ok(p.start > 0)
  assert.equal(p.start + p.count <= 20480, true)
})

test('a short record is not capped even for WVD', () => {
  const p = costPlan('wvd', 1000, 1024)
  assert.equal(p.capped, false)
  assert.equal(p.count, 1000)
})

test('a record exactly at the cap is left alone', () => {
  assert.equal(costPlan('wvd', EXPLORER_MAX_SAMPLES, 1024).capped, false)
})

// ── payload shapes ───────────────────────────────────────────────────────────

test('each transform knows which key its surface arrives under', () => {
  assert.equal(surfaceOf('stft', { magnitude: 'M' }), 'M')
  assert.equal(surfaceOf('cwt', { magnitude: 'M' }), 'M')
  assert.equal(surfaceOf('wvd', { wvd: 'W' }), 'W')
  assert.equal(surfaceOf('spwvd', { spwvd: 'S' }), 'S')
  assert.equal(surfaceOf('stft', null), null)
})

test('every transform has an endpoint and an unknown id falls back safely', () => {
  for (const t of TRANSFORMS) assert.match(t.endpoint, /^\/api\/timefreq\//)
  assert.equal(transformById('nonsense').id, 'stft')
})

// ── the composed chart ───────────────────────────────────────────────────────

const T = {
  paper: '#fff', bg: '#fff', text: '#000', grid: '#eee', title: '#000',
  legend: '#fff', border: '#ccc', danger: '#f00', warning: '#fa0',
  series: ['#1', '#2', '#3'],
}
const surface = {
  times: [0, 1, 2, 3], freqs: [10, 20, 30], z,
}
const base = {
  tf: surface, transform: 'stft',
  ts: { times: [0, 1, 2, 3], values: [1, 2, 3, 4], name: 'acc1' },
  psd: { freqs: [10, 20, 30], values: [1, 2, 3] },
}
const ex = (over = {}) => buildExplorer({ ...base, ...over }, { T, units: { focus: 'g' } })

test('the three panels share the axes that make them comparable', () => {
  const { layout } = ex()
  // The time series sits above the surface on the same time axis, and the PSD
  // to its right on the same frequency axis. That sharing is the whole layout.
  assert.equal(layout.yaxis2.anchor, 'x', 'time series hangs off the time axis')
  assert.equal(layout.xaxis2.anchor, 'y', 'PSD hangs off the frequency axis')
  assert.equal(layout.yaxis.title, 'Frequency [Hz]')
  assert.equal(layout.xaxis.title, 'Time [s]')
})

test('the panels do not overlap vertically', () => {
  const { layout } = ex()
  assert.ok(layout.yaxis.domain[1] <= layout.yaxis2.domain[0],
    'the surface must end below where the time series begins')
})

test('units reach the composed panels too', () => {
  const { layout } = ex()
  assert.equal(layout.yaxis2.title.text, 'Signal [g]')
  assert.equal(layout.xaxis2.title.text, 'PSD [g²/Hz]')
})

test('picking a frequency adds a fourth panel rather than a second y-axis', () => {
  // Overlaying energy-over-time on the time series would put two unrelated
  // scales in one panel -- the dual-axis mistake TODO §3.4 describes.
  const withPick = ex({ pick: { freq: 20, freqIndex: 1, envelope: [5, 6, 7, 8] } })
  assert.ok(withPick.layout.yaxis3, 'a fourth panel appears')
  assert.equal(withPick.layout.yaxis3.anchor, 'x3')
  const slice = withPick.traces.find(t => t.yaxis === 'y3')
  assert.ok(slice, 'the envelope is drawn on its own axis')
  assert.deepEqual(slice.y, [5, 6, 7, 8])
  // and it shares the time axis with everything above it
  assert.equal(withPick.layout.xaxis3.matches, 'x')
})

test('without a pick there is no fourth panel wasting the space', () => {
  assert.equal(ex().layout.yaxis3, undefined)
})

test('a picked instant draws its spectrum against the average, on one axis', () => {
  const withPick = ex({ pick: { time: 1, timeIndex: 1, spectrum: spectrumAt(z, 1) } })
  const onPsdPanel = withPick.traces.filter(t => t.xaxis === 'x2')
  assert.equal(onPsdPanel.length, 2, 'the average PSD and the cursor spectrum')
  // Same panel, same scale -- which is what makes them comparable.
  assert.deepEqual(onPsdPanel[1].y, surface.freqs)
  assert.deepEqual(onPsdPanel[1].x, [2, 6, 10])
})

test('crosshairs mark where the slices were taken', () => {
  const { layout } = ex({ pick: { time: 2, timeIndex: 2, freq: 20, freqIndex: 1 } })
  assert.equal(layout.shapes.length, 2)
  assert.ok(layout.shapes.some(s => s.x0 === 2 && s.x1 === 2), 'a vertical line at t')
  assert.ok(layout.shapes.some(s => s.y0 === 20 && s.y1 === 20), 'a horizontal line at f')
})

test('the colour scale is one scale for every transform', () => {
  // The reason the Explorer exists: four surfaces that cannot be compared
  // because each tab scaled its own colours independently.
  const opts = { T, tf: { db: true, rangeDb: 40 }, units: {} }
  const a = buildExplorer({ ...base, transform: 'stft' }, opts)
  const b = buildExplorer({ ...base, transform: 'wvd' }, opts)
  assert.equal(a.traces[0].zmin, b.traces[0].zmin)
  assert.equal(a.traces[0].zmax, b.traces[0].zmax)
  assert.equal(a.traces[0].zmin, -40)
})

test('WVD keeps a bare colourbar while STFT carries the signal unit', () => {
  const opts = { T, tf: { db: false }, units: { focus: 'g' } }
  assert.equal(
    buildExplorer({ ...base, transform: 'stft' }, opts).traces[0].colorbar.title.text,
    'magnitude [g]')
  assert.equal(
    buildExplorer({ ...base, transform: 'wvd' }, opts).traces[0].colorbar.title.text,
    'magnitude')
})

test('an empty or missing surface builds nothing rather than a broken chart', () => {
  assert.equal(buildExplorer(null, { T }), null)
  assert.equal(buildExplorer({ tf: null }, { T }), null)
  assert.equal(buildExplorer({ tf: { times: [], freqs: [], z: [] } }, { T }), null)
})

test('the surface alone is enough; the side panels are optional', () => {
  const spec = buildExplorer({ tf: surface, transform: 'stft' }, { T, units: {} })
  assert.ok(spec, 'a surface with no timeseries or PSD yet still draws')
  assert.equal(spec.traces.length, 1)
})
