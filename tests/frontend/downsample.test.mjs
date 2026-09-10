// Zooming must buy resolution: the point budget is spent on the visible window,
// not on the whole record. Without this, zooming in just magnifies a decimated
// curve into steps.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { downsampleXY, MAX_PLOT_POINTS, isDownsampledFor }
  from '../../frontend/src/lib/plotSpec.js'
import { timeseries } from './helpers.mjs'

const fs = 1000
const { times_raw: x, signals } = timeseries(200, fs)   // 200 s => 200k samples
const y = signals[0].signal_raw

test('unzoomed view fits the point budget', () => {
  const d = downsampleXY(x, y, true, null)
  assert.ok(d.x.length <= MAX_PLOT_POINTS, `${d.x.length} points`)
  assert.ok(d.x.length > MAX_PLOT_POINTS / 2, 'and does not waste the budget')
})

test('unzoomed view is decimated below the raw sample rate', () => {
  const d = downsampleXY(x, y, true, null)
  assert.ok(d.x[1] - d.x[0] > 1 / fs)
})

test('a 1 s window is drawn at the full sample rate', () => {
  const d = downsampleXY(x, y, true, [10, 11])
  assert.ok(Math.abs((d.x[1] - d.x[0]) - 1 / fs) < 1e-9,
            `dt ${d.x[1] - d.x[0]} vs raw ${1 / fs}`)
  assert.ok(d.x.length >= 1000 && d.x.length <= 1010, `${d.x.length} points`)
})

test('zooming increases resolution', () => {
  const full = downsampleXY(x, y, true, null)
  const zoom = downsampleXY(x, y, true, [10, 11])
  assert.ok((zoom.x[1] - zoom.x[0]) < (full.x[1] - full.x[0]))
})

test('the window covers the requested range, with a margin', () => {
  const d = downsampleXY(x, y, true, [10, 11])
  assert.ok(d.x[0] <= 10, 'reaches the left edge')
  assert.ok(d.x[d.x.length - 1] >= 11, 'reaches the right edge')
})

test('x and y stay paired after windowing', () => {
  const d = downsampleXY(x, y, true, [10, 11])
  const drift = d.x.reduce(
    (m, t, i) => Math.max(m, Math.abs(d.y[i] - Math.sin(2 * Math.PI * 7 * t))), 0)
  assert.ok(drift < 1e-12, `max drift ${drift}`)
})

test('a window wider than the budget is decimated, not truncated', () => {
  const d = downsampleXY(x, y, true, [0, 199])
  assert.ok(d.x.length <= MAX_PLOT_POINTS, `${d.x.length} points`)
  assert.ok(d.x[d.x.length - 1] > 198, 'still reaches its end')
})

test('degenerate inputs are safe', () => {
  assert.equal(downsampleXY([], [], true, [0, 1]).x.length, 0, 'empty input')
  assert.ok(downsampleXY(x, y, true, [500, 600]).x.length <= 2, 'range past the end')
  assert.equal(downsampleXY(x, y, true, [11, 10]).x.length, 0, 'inverted range')
})

test('decimation can be turned off entirely', () => {
  assert.equal(downsampleXY(x, y, false, null).x.length, x.length)
})

test('isDownsampledFor only claims tabs that actually decimate', () => {
  const long = { times_raw: x }
  assert.ok(isDownsampledFor('timeseries', long))
  assert.ok(!isDownsampledFor('fft', long), 'spectra are not decimated')
  assert.ok(!isDownsampledFor('timeseries', { times_raw: [1, 2, 3] }), 'short record')
})


// ── peaks must survive the thinning ─────────────────────────────────────────
//
// The bug these guard: decimating by stride deleted whatever fell between the
// samples it kept. On a 600k-bin FFT thinned to the budget, a one-bin peak was
// drawn 8% of the time. A chart that silently omits the resonance you are
// looking for is worse than a slow one.

test('a one-bin peak survives wherever it falls', () => {
  const n = 600_000
  const x = Array.from({ length: n }, (_, i) => i)
  const y = new Array(n).fill(1)
  // Deliberately awkward positions: just inside, just outside and far from a
  // bin edge, plus the two ends.
  for (const peak of [0, 1, 11, 12, 13, 4999, 300_000, 599_998, n - 1]) {
    y[peak] = 1000
    const d = downsampleXY(x, y, true, null)
    assert.ok(d.y.includes(1000), `peak at index ${peak} was dropped`)
    y[peak] = 1
  }
})

test('a one-sample dropout survives too, not just a spike', () => {
  const n = 200_000
  const x = Array.from({ length: n }, (_, i) => i)
  const y = new Array(n).fill(1)
  y[123_457] = -50
  const d = downsampleXY(x, y, true, null)
  assert.ok(d.y.includes(-50), 'the minimum of the bin must be kept as well')
})

test('the thinned series still runs left to right', () => {
  // Two points per bin means emitting a min and a max; out of order they would
  // draw a line that doubles back on itself.
  const n = 300_000
  const x = Array.from({ length: n }, (_, i) => i)
  const y = Array.from({ length: n }, (_, i) => Math.sin(i / 7) + Math.sin(i / 991))
  const d = downsampleXY(x, y, true, null)
  for (let i = 1; i < d.x.length; i++) {
    assert.ok(d.x[i] >= d.x[i - 1], `x went backwards at ${i}`)
  }
})

test('thinning still respects the budget', () => {
  const n = 1_200_000
  const x = Array.from({ length: n }, (_, i) => i)
  const y = Array.from({ length: n }, (_, i) => i % 97)
  const d = downsampleXY(x, y, true, null)
  assert.ok(d.x.length <= MAX_PLOT_POINTS, `${d.x.length} points`)
  assert.equal(d.x.length, d.y.length)
})

test('the extremes of the whole record are on the chart', () => {
  const n = 400_000
  const x = Array.from({ length: n }, (_, i) => i)
  const y = Array.from({ length: n }, (_, i) => Math.sin(i / 1000))
  y[77_777] = 12.5
  y[300_001] = -9.5
  const d = downsampleXY(x, y, true, null)
  assert.equal(Math.max(...d.y), 12.5)
  assert.equal(Math.min(...d.y), -9.5)
})
