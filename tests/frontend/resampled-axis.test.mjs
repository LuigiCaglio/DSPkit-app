// On a resampled record the spectrum stops at the new Nyquist, but the filter
// response is designed at the original rate and spans the old one. It must not
// stretch the frequency axis past the last bin.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot } from '../../frontend/src/lib/plotSpec.js'
import { T } from './helpers.mjs'

const freqs = Array.from({ length: 26 }, (_, i) => i)          // 0..25 Hz: fs 50
const response = {
  freqs: Array.from({ length: 414 }, (_, i) => i),              // 0..413 Hz: fs 826
  magnitude: Array.from({ length: 414 }, (_, i) => (i < 20 ? 1 : 0)),
}
const maxX = (spec) => Math.max(...spec.traces.flatMap(t => t.x ?? []))

test('psd: the filter response stops at the spectrum\'s Nyquist', () => {
  const d = { freqs, signals: [{ name: 'a', Pxx: freqs.map(() => 1) }] }
  const spec = buildPlot('psd', d, { T, response })
  assert.equal(maxX(spec), 25)
  assert.ok(spec.traces.some(t => t.name === 'filter response'))
})

test('fft: the filter response stops at the spectrum\'s Nyquist', () => {
  const d = { freqs, signals: [{ name: 'a', amplitude: freqs.map(() => 1) }] }
  const spec = buildPlot('fft', d, { T, response })
  assert.equal(maxX(spec), 25)
})
