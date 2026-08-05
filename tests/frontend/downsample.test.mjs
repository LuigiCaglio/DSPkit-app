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
