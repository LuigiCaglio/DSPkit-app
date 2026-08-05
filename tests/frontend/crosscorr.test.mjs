// Lag sign carries the lead/lag direction, so restricting the view to one half
// must not change the data -- and the reported peak must belong to the half you
// are looking at, not the whole record.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot, buildPairOverlay } from '../../frontend/src/lib/plotSpec.js'
import { T, lagAxis, bump } from './helpers.mjs'

const lags = lagAxis()
// Strongest at +0.30 s, with a weaker anticorrelation at -0.62 s, so the two
// halves have genuinely different answers.
const ccf = lags.map((t, i) =>
  bump(lags, 0.30, 0.9)[i] - bump(lags, -0.62, 0.5)[i])
const d = { lags, ccf }
const spec = (lagSide) => buildPlot('cross_correlation', d, { T, lagSide })
const peakOf = (s) => s.traces.find(t => t.mode === 'markers')

test('both: the axis autoranges', () => {
  assert.equal(spec('both').layout.xaxis.autorange, true)
  assert.equal(spec('both').layout.xaxis.range, undefined)
})

test('positive: the axis is [0, maxLag]', () => {
  assert.deepEqual(spec('positive').layout.xaxis.range, [0, 1])
})

test('negative: the axis is [minLag, 0]', () => {
  assert.deepEqual(spec('negative').layout.xaxis.range, [-1, 0])
})

test('the full trace is kept in every mode -- the view is restricted, not the data', () => {
  for (const side of ['both', 'positive', 'negative'])
    assert.equal(spec(side).traces[0].x.length, lags.length, side)
})

test('the marked peak belongs to the visible half', () => {
  assert.ok(Math.abs(peakOf(spec('both')).x[0] - 0.30) < 1e-9, 'both -> global max')
  assert.ok(Math.abs(peakOf(spec('positive')).x[0] - 0.30) < 1e-9, 'positive')
  assert.ok(Math.abs(peakOf(spec('negative')).x[0] + 0.62) < 1e-9,
            'negative -> its own max, not the global one')
})

test('|CCF| is used, so a strong anticorrelation still registers', () => {
  assert.ok(peakOf(spec('negative')).y[0] < 0)
})

test('the title states the lag actually marked', () => {
  assert.match(spec('positive').layout.title.text, /0\.3/)
  assert.match(spec('negative').layout.title.text, /-0\.62/)
})

test('a one-sided record survives being asked for its empty half', () => {
  const s = buildPlot('cross_correlation',
                      { lags: [0, 0.1, 0.2], ccf: [1, 0.5, 0.2] },
                      { T, lagSide: 'negative' })
  assert.ok(s.traces.length >= 1)
})

// ── overlay: one reference against several channels ────────────────────────
const items = [
  { name: 'A (self)', data: { lags, ccf: bump(lags, 0, 1.0) } },
  { name: 'A → B',    data: { lags, ccf: bump(lags, 0.20, 0.9) } },
  { name: 'A → C',    data: { lags, ccf: bump(lags, -0.40, 0.7) } },
]

test('overlay draws one named, distinctly coloured line per comparison', () => {
  const s = buildPairOverlay('cross_correlation', items, { T, ref: 'A' })
  const lines = s.traces.filter(t => t.mode === 'lines')
  assert.equal(lines.length, 3)
  assert.deepEqual(lines.map(l => l.name), items.map(i => i.name))
  assert.equal(new Set(lines.map(l => l.line.color)).size, 3)
})

test('overlay keeps the self comparison first, as the baseline', () => {
  const s = buildPairOverlay('cross_correlation', items, { T, ref: 'A' })
  assert.match(s.traces[0].name, /self/)
})

test('overlay marks each curve its own peak, not one global peak', () => {
  const pk = peakOf(buildPairOverlay('cross_correlation', items, { T, ref: 'A' }))
  assert.equal(pk.x.length, 3)
  assert.ok(Math.abs(pk.x[1] - 0.20) < 1e-9)
  assert.ok(Math.abs(pk.x[2] + 0.40) < 1e-9)
})

test('overlay peaks respect the visible half too', () => {
  const s = buildPairOverlay('cross_correlation', items, { T, ref: 'A', lagSide: 'positive' })
  assert.ok(peakOf(s).x.every(v => v >= 0), JSON.stringify(peakOf(s).x))
})

test('overlay titles name the reference and the count', () => {
  const s = buildPairOverlay('cross_correlation', items, { T, ref: 'A' })
  assert.match(s.layout.title.text, /A vs 3 channels/)
})

test('coherence and csd overlays use their own axes', () => {
  const freqs = [0, 1, 2, 3]
  const co = buildPairOverlay('coherence', [
    { name: 'A → B', data: { freqs, Cxy: [1, .9, .5, .2] } },
  ], { T, ref: 'A' })
  assert.deepEqual(co.layout.yaxis.range, [0, 1], 'coherence is bounded 0..1')

  const cs = buildPairOverlay('csd', [
    { name: 'A → B', data: { freqs, magnitude: [1, 2, 3, 4] } },
  ], { T, ref: 'A' })
  assert.equal(cs.layout.yaxis.title, '|CSD|')
})

test('a failed comparison is skipped rather than sinking the rest', () => {
  const s = buildPairOverlay('cross_correlation',
                             [items[0], { name: 'A → X', error: 'boom' }], { T, ref: 'A' })
  assert.equal(s.traces.filter(t => t.mode === 'lines').length, 1)
})

test('an all-failed overlay returns null instead of an empty chart', () => {
  assert.equal(
    buildPairOverlay('cross_correlation', [{ name: 'A → X', error: 'boom' }], { T }),
    null)
})
