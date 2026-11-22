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
