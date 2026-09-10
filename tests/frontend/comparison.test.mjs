// Two datasets on one chart. buildComparison deliberately has no per-tab
// knowledge — it builds each dataset with the ordinary buildPlot and merges —
// so what is worth pinning is the merge itself: that the tab's own axes
// survive, that datasets are told apart without stealing the channel's colour,
// and that one dataset failing does not take the chart down with it.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, buildComparison } from '../../frontend/src/lib/plotSpec.js'
import { COMPARABLE, isComparable } from '../../frontend/src/lib/analyses.js'
import { T } from './helpers.mjs'

const freqs = [1, 2, 3, 4]

const psd = (scale) => ({
  freqs,
  signals: [
    { name: 'acc1', psd: freqs.map(f => scale / f) },
    { name: 'acc2', psd: freqs.map(f => scale / (f * 2)) },
  ],
})

const units = { signal: 'g', focus: 'g', byName: { acc1: 'g', acc2: 'g' } }
const opts = (extra = {}) => ({ T, units, ...extra })

const items = (a = psd(1), b = psd(10)) => ([
  { label: 'today.csv', data: a },
  { label: 'baseline.csv', data: b },
])

test('every trace from both datasets reaches the chart', () => {
  const spec = buildComparison('psd', items(), opts())
  assert.equal(spec.traces.length, 4)
})

test('each trace says which dataset it came from', () => {
  const names = buildComparison('psd', items(), opts()).traces.map(t => t.name)
  assert.deepEqual(names, [
    'acc1 · today.csv', 'acc2 · today.csv',
    'acc1 · baseline.csv', 'acc2 · baseline.csv',
  ])
})

test('datasets are separated by dash, never by colour', () => {
  // The regression this guards: recolouring by dataset. Colour is the channel,
  // and matching acc1 to acc1 across the two files is the whole point of the
  // chart — recolour and that pairing is gone.
  const spec = buildComparison('psd', items(), opts())
  const [a1, a2, b1, b2] = spec.traces
  assert.equal(a1.line.color, b1.line.color)
  assert.equal(a2.line.color, b2.line.color)
  assert.notEqual(a1.line.color, a2.line.color)
  assert.equal(a1.line.dash, 'solid')
  assert.equal(b1.line.dash, 'dot')
})

test("the tab's own axes and units survive the merge", () => {
  const solo = buildPlot('psd', psd(1), opts())
  const both = buildComparison('psd', items(), opts())
  assert.equal(both.layout.yaxis.title, solo.layout.yaxis.title)
  assert.equal(both.layout.xaxis.title, solo.layout.xaxis.title)
  assert.equal(both.layout.yaxis.type, solo.layout.yaxis.type)
})

test('a log y axis asked for by the tab is still a log y axis', () => {
  const both = buildComparison('psd', items(), opts({ yLog: true }))
  assert.equal(both.layout.yaxis.type, 'log')
})

test('the title names both datasets', () => {
  const text = buildComparison('psd', items(), opts()).layout.title.text
  assert.match(text, /today\.csv vs baseline\.csv/)
})

test('one dataset failing still draws the other', () => {
  const spec = buildComparison('psd',
    [{ label: 'today.csv', data: psd(1) },
     { label: 'baseline.csv', data: null, error: 'boom' }], opts())
  assert.equal(spec.traces.length, 2)
  assert.match(spec.layout.title.text, /today\.csv/)
  assert.doesNotMatch(spec.layout.title.text, /vs baseline/)
})

test('both failing returns nothing rather than an empty chart', () => {
  const spec = buildComparison('psd',
    [{ label: 'a', data: null, error: 'x' },
     { label: 'b', data: null, error: 'y' }], opts())
  assert.equal(spec, null)
})

test('a tab whose traces are not lines falls back to one dataset', () => {
  // The backstop for a tab added to COMPARABLE without thought. A heatmap
  // cannot be overlaid on another heatmap; showing the active dataset alone is
  // wrong-but-readable, where merging would be unreadable.
  const stft = {
    times: [0, 1], freqs: [1, 2],
    magnitude: [[1, 2], [3, 4]],
  }
  const spec = buildComparison('stft',
    [{ label: 'a', data: stft }, { label: 'b', data: stft }], opts())
  const solo = buildPlot('stft', stft, opts())
  assert.equal(spec.traces.length, solo.traces.length)
})

test('the comparable set excludes the surfaces and the raw time series', () => {
  for (const tab of ['stft', 'cwt', 'wvd', 'spwvd', 'explorer', 'timeseries']) {
    assert.equal(isComparable(tab), false, `${tab} must not be comparable`)
  }
  for (const tab of ['psd', 'fft', 'fdd', 'predictability']) {
    assert.equal(COMPARABLE.has(tab), true, `${tab} should be comparable`)
  }
})
