// A linear-magnitude spectrogram of real data is one bright ridge on a black
// field, because the dynamic range spans decades. dB relative to the peak with
// an explicit range is what makes the structure visible.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, toDecibels, HEATMAP_SCALES } from '../../frontend/src/lib/plotSpec.js'
import { T } from './helpers.mjs'

/** One strong ridge plus structure 40 dB down — invisible on a linear ramp. */
function surface() {
  const z = []
  for (let f = 0; f < 20; f++) {
    const row = []
    for (let t = 0; t < 30; t++) {
      row.push(f === 10 ? 1.0 : f === 4 ? 0.01 : 1e-5)
    }
    z.push(row)
  }
  return { times: [...Array(30).keys()], freqs: [...Array(20).keys()], magnitude: z }
}

const d = surface()
const spec = (tf) => buildPlot('stft', d, { T, tf })
const trace = (tf) => spec(tf).traces[0]

test('dB is the default for time-frequency surfaces', () => {
  const t0 = trace({})
  assert.equal(t0.zmax, 0, 'peak sits at 0 dB')
  assert.equal(t0.zmin, -60, 'default range is 60 dB below peak')
  assert.equal(t0.zauto, false, 'the range is explicit, not auto')
})

test('dB is relative to the surface peak', () => {
  const z = trace({ db: true, rangeDb: 60 }).z
  assert.ok(Math.abs(z[10][0] - 0) < 1e-9, 'the ridge is 0 dB')
  assert.ok(Math.abs(z[4][0] - (-40)) < 1e-9, 'a 0.01 amplitude is -40 dB')
})

test('the dynamic range clamps rather than leaving gaps', () => {
  const z = trace({ db: true, rangeDb: 60 }).z
  // 1e-5 is -100 dB, past the floor.
  assert.equal(z[0][0], -60, 'below-floor values clamp to the floor')
  assert.ok(z.every(r => r.every(Number.isFinite)), 'no -Infinity, which renders as holes')
})

test('a narrower range crushes more of the background', () => {
  const wide = trace({ db: true, rangeDb: 90 }).z
  const narrow = trace({ db: true, rangeDb: 30 }).z
  assert.equal(wide[4][0], -40, '-40 dB survives a 90 dB range')
  assert.equal(narrow[4][0], -30, 'and is clamped by a 30 dB range')
})

test('quasi-probability distributions with negative values still work', () => {
  // WVD and SPWVD go negative; a raw log of those produces NaN holes.
  const wvd = { times: [0, 1], freqs: [0, 1], wvd: [[-1, 0.5], [0.25, -0.125]] }
  const s = buildPlot('wvd', wvd, { T, tf: { db: true, rangeDb: 60 } })
  const z = s.traces[0].z
  assert.ok(z.every(r => r.every(Number.isFinite)), 'no NaN from logging a negative')
  assert.ok(Math.abs(z[0][0] - 0) < 1e-9, 'magnitude is taken, so -1 is the peak')
  assert.ok(Math.abs(z[1][1] - (20 * Math.log10(0.125))) < 1e-9, 'other cells scale correctly')
})

test('an all-zero surface does not divide by zero', () => {
  const flat = { times: [0, 1], freqs: [0, 1], magnitude: [[0, 0], [0, 0]] }
  const s = buildPlot('stft', flat, { T, tf: { db: true } })
  assert.ok(s.traces[0].z.every(r => r.every(v => Number.isFinite(v) || v === 0)))
})

test('linear mode clips the top percentile instead of letting outliers own the ramp', () => {
  const t0 = trace({ db: false, clipPct: 99 })
  assert.ok(t0.zmax != null && t0.zmax <= 1.0, 'an explicit ceiling is set')
  assert.equal(t0.z, d.magnitude, 'linear mode leaves the data untransformed')
})

test('the colour ramp is configurable, and only perceptually uniform ones ship', () => {
  assert.equal(trace({ colorscale: 'Cividis' }).colorscale, 'Cividis')
  assert.deepEqual(HEATMAP_SCALES, ['Viridis', 'Cividis', 'Magma', 'Inferno'])
  for (const bad of ['Jet', 'Rainbow', 'Turbo', 'Portland'])
    assert.ok(!HEATMAP_SCALES.includes(bad), `${bad} is not perceptually uniform`)
})

test('the colorbar names its units', () => {
  assert.match(trace({ db: true }).colorbar.title.text, /dB/)
  assert.match(trace({ db: false }).colorbar.title.text, /magnitude/)
})

test('every time-frequency tab uses the same scaling', () => {
  const payloads = {
    stft:  { times: [0, 1], freqs: [0, 1], magnitude: [[1, 0.5], [0.25, 0.1]] },
    cwt:   { times: [0, 1], freqs: [0, 1], magnitude: [[1, 0.5], [0.25, 0.1]] },
    wvd:   { times: [0, 1], freqs: [0, 1], wvd:       [[1, 0.5], [0.25, 0.1]] },
    spwvd: { times: [0, 1], freqs: [0, 1], spwvd:     [[1, 0.5], [0.25, 0.1]] },
  }
  for (const [tab, payload] of Object.entries(payloads)) {
    const s = buildPlot(tab, payload, { T, tf: { db: true, rangeDb: 60 } })
    assert.equal(s.traces[0].zmin, -60, `${tab} honours the range`)
    assert.equal(s.traces[0].zmax, 0, `${tab} peaks at 0 dB`)
  }
})

test('toDecibels is exported and independently usable', () => {
  const { z, zmin, zmax } = toDecibels([[1, 0.1]], 40)
  assert.equal(zmax, 0)
  assert.equal(zmin, -40)
  assert.ok(Math.abs(z[0][1] - (-20)) < 1e-9)
})
