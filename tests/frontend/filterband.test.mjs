// Filter cutoffs are picked from the spectrum, so the spectrum has to show what
// the filter removes. Picking is an explicit horizontal selection -- the default
// drag zooms, which is not a selection and gives no feedback.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot } from '../../frontend/src/lib/plotSpec.js'
import { T, spectrum } from './helpers.mjs'

const psd = spectrum('Pxx')
const fft = spectrum('amplitude')
const psdWith = (opts) => buildPlot('psd', psd, { T, ...opts })

test('no filter means no shading', () => {
  assert.equal(psdWith({ band: null }).layout.shapes, undefined)
  assert.equal(psdWith({ band: { hp: null, lp: null } }).layout.shapes, undefined)
})

test('a high-pass shades everything below the cutoff', () => {
  const s = psdWith({ band: { hp: 10, lp: null } }).layout.shapes
  assert.equal(s.length, 1)
  assert.equal(s[0].x0, 0)
  assert.equal(s[0].x1, 10)
})

test('a low-pass shades everything above the cutoff', () => {
  const s = psdWith({ band: { hp: null, lp: 200 } }).layout.shapes
  assert.equal(s[0].x0, 200)
  assert.equal(s[0].x1, 500)
})

test('a band-pass shades both sides and leaves the pass band clear', () => {
  const s = psdWith({ band: { hp: 10, lp: 200 } }).layout.shapes
  assert.equal(s.length, 2)
  assert.equal(s[0].x1, 10)
  assert.equal(s[1].x0, 200)
})

test('shading sits under the trace, spans the full height, and stays translucent', () => {
  const s = psdWith({ band: { hp: 10, lp: 200 } }).layout.shapes
  assert.ok(s.every(r => r.layer === 'below'), 'below the data')
  assert.ok(s.every(r => r.yref === 'paper' && r.y0 === 0 && r.y1 === 1), 'full height')
  assert.ok(s.every(r => r.opacity < 0.2), 'does not obscure the spectrum')
})

test('shading does not disturb the rest of the spec', () => {
  const s = psdWith({ band: { hp: 10, lp: 200 } })
  assert.equal(s.traces.length, 1)
  assert.equal(s.layout.yaxis.type, 'log', 'psd keeps its log-y default')

  const ranged = psdWith({ band: { hp: 10, lp: 200 },
                           psd: { yLog: false, xMin: 5, xMax: 300 } })
  assert.equal(ranged.layout.xaxis.range[0], 5, 'manual axis range still applies')
  assert.equal(ranged.layout.yaxis.type, 'linear')
})

test('the FFT shows the band too, so it can be picked there as well', () => {
  assert.equal(buildPlot('fft', fft, { T, band: { hp: 10, lp: 200 } }).layout.shapes.length, 2)
  assert.equal(buildPlot('fft', fft, { T, band: null }).layout.shapes, undefined)
})

test('picking mode is a horizontal selection, not a zoom', () => {
  const s = psdWith({ dragmode: 'select' }).layout
  assert.equal(s.dragmode, 'select')
  assert.equal(s.selectdirection, 'h', 'x-only: a band has no y extent')
  assert.equal(psdWith({}).layout.dragmode, undefined, 'off by default')
  assert.equal(buildPlot('fft', fft, { T, dragmode: 'select' }).layout.dragmode, 'select')
})
