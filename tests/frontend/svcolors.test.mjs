// FDD singular values are ordered, not categorical. Drawn in the channel
// palette, SV1 / SV2 / SV3 were read as channels 1 / 2 / 3 next to the PSD in
// the Overview. They now use a neutral ramp that shares no colour with it.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, svColors } from '../../frontend/src/lib/plotSpec.js'
import { T } from './helpers.mjs'

const fdd = {
  freqs: [1, 2, 3, 4],
  S: [[4, 2, 1], [8, 2, 1], [4, 2, 1], [2, 1, 0.5]],
  labels: ['a', 'b', 'c'],
  peak_freqs: [],
}

test('SV curves never use a channel colour', () => {
  const { traces } = buildPlot('fdd', fdd, { T })
  const cols = traces.map(t => t.line.color)
  assert.equal(cols.length, 3)
  for (const c of cols) assert.ok(!T.series.includes(c), `${c} is a channel colour`)
  assert.equal(new Set(cols).size, 3)
})

test('SV1 is the strongest line: thickest, nearest the text colour', () => {
  const { traces } = buildPlot('fdd', fdd, { T })
  assert.ok(traces[0].line.width > traces[1].line.width)
  const lum = h => [1, 3, 5].reduce((s, i) => s + parseInt(h.slice(i, i + 2), 16), 0)
  const light = svColors({ mode: 'light' }, 3), dark = svColors({ mode: 'dark' }, 3)
  assert.ok(lum(light[0]) < lum(light[2]), 'light theme: SV1 darkest')
  assert.ok(lum(dark[0]) > lum(dark[2]), 'dark theme: SV1 brightest')
})

test('one channel gives one valid colour', () => {
  const c = svColors({ mode: 'dark' }, 1)
  assert.equal(c.length, 1)
  assert.match(c[0], /^#[0-9a-f]{6}$/)
})

// FDD scale: dB by default, linear on request (Log Y unticked).
test('FDD is in dB unless Log Y is explicitly off', () => {
  const def = buildPlot('fdd', fdd, { T })
  assert.equal(def.traces[0].y[1], 10 * Math.log10(8))
  assert.match(def.layout.yaxis.title, /dB/)
  assert.equal(def.layout.yaxis.type, 'linear')       // never a log axis on dB values
  const on = buildPlot('fdd', fdd, { T, yLog: true })
  assert.deepEqual(on.traces[0].y, def.traces[0].y)
})

test('FDD linear: raw singular values, axis in PSD units', () => {
  const lin = buildPlot('fdd', fdd, { T, yLog: false, units: { signal: 'm/s²' } })
  assert.deepEqual(lin.traces[0].y, [4, 8, 4, 2])
  assert.doesNotMatch(lin.layout.yaxis.title, /dB/)
  assert.match(lin.layout.yaxis.title, /Singular value/)
  assert.equal(lin.layout.yaxis.type, 'linear')
})

// Singular-vector column charts.
const fv = {
  labels: ['a', 'b', 'c'],
  points: [
    { freq_used: 3.27, vectors: [
      { sv: 1, singular_value: 2e-3, real: [1, -0.5, 0.2], magnitude: [1, 0.5, 0.2], phase_deg: [0, 180, 0] },
      { sv: 2, singular_value: 1e-4, real: [0.1, 0.9, -0.4], magnitude: [0.1, 0.9, 0.4], phase_deg: [0, 0, 180] },
    ]},
    { freq_used: 3.69, vectors: [
      { sv: 1, singular_value: 5e-3, real: [0.3, 0.3, 1], magnitude: [0.3, 0.3, 1], phase_deg: [0, 0, 0] },
      { sv: 2, singular_value: 2e-4, real: [0.7, -0.7, 0], magnitude: [0.7, 0.7, 0], phase_deg: [0, 180, 0] },
    ]},
  ],
}

test('one column chart per picked frequency, one bar group per vector', async () => {
  const { buildSvBars } = await import('../../frontend/src/lib/plotSpec.js')
  const charts = buildSvBars(fv, { T })
  assert.equal(charts.length, 2)
  const c = charts[0].spec
  assert.deepEqual(c.traces.map(t => t.name), ['SV1', 'SV2'])
  assert.ok(c.traces.every(t => t.type === 'bar'))
  assert.deepEqual(c.traces[0].x, ['a', 'b', 'c'])
  assert.deepEqual(c.traces[0].y, [1, -0.5, 0.2])                 // signed: real part
  assert.deepEqual(c.layout.yaxis.range, [-1.05, 1.05])
  assert.match(c.layout.title.text, /3\.27 Hz.*σ1.*σ2/)
  assert.ok(!T.series.includes(c.traces[0].marker.color))          // not a channel colour
  const p = buildSvBars(fv, { T, form: 'polar' })[1].spec
  assert.deepEqual(p.traces[1].y, [0.7, 0.7, 0])                   // polar: magnitude
  assert.deepEqual(p.layout.yaxis.range, [0, 1.05])
})

test('a single vector draws without a legend', async () => {
  const { buildSvBars } = await import('../../frontend/src/lib/plotSpec.js')
  const one = { labels: fv.labels, points: [{ ...fv.points[0], vectors: [fv.points[0].vectors[0]] }] }
  const s = buildSvBars(one, { T })[0].spec
  assert.equal(s.traces.length, 1)
  assert.equal(s.layout.showlegend, false)
})
