// The Windowed statistics tab (formerly "SHM indicators"): five stacked panels,
// each axis saying what it is and how to read it.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot } from '../../frontend/src/lib/plotSpec.js'
import { T } from './helpers.mjs'

const d = {
  times: [1, 3, 5], w_rms: [1, 2, 1], w_mean: [0, 0, 0], w_peak: [3, 9, 3],
  w_crest: [3, 4.5, 3], w_kurtosis: [0.1, 8, -0.2], w_dominant_freq: [4, 4, 4],
  w_entropy: [0.3, 0.6, 0.3], spectral_entropy: 0.4, kurtosis: 2.1, skewness: 0.1,
  rms: 1.4, excess: true, window_duration: 2, n_windows: 3, df: 0.1,
}

test('five panels, each axis titled with its meaning', () => {
  const { traces, layout } = buildPlot('indicators', d, { T, units: { focus: 'm/s²' } })
  const titles = ['yaxis', 'yaxis2', 'yaxis3', 'yaxis4', 'yaxis5'].map(k => layout[k].title.text)
  assert.match(titles[0], /RMS.*m\/s²/)
  assert.match(titles[1], /Crest factor.*peak \/ RMS/s)
  assert.match(titles[2], /Excess kurtosis.*0 = Gaussian/s)
  assert.match(titles[3], /Dominant.*\[Hz\]/s)
  assert.match(titles[4], /entropy.*0 tone, 1 white/s)
  assert.deepEqual(layout.yaxis5.range, [0, 1])
  assert.equal(traces.filter(t => t.name !== 'Gaussian').length, 5)
  assert.match(layout.xaxis.title, /window centres/)
  assert.match(layout.title.text, /3 windows of 2 s/)
})

test('plain kurtosis moves the Gaussian reference to 3', () => {
  const { traces, layout } = buildPlot('indicators', { ...d, excess: false }, { T })
  assert.match(layout.yaxis3.title.text, /^Kurtosis.*3 = Gaussian/s)
  assert.deepEqual(traces.find(t => t.name === 'Gaussian').y, [3, 3])
})
