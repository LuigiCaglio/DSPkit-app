// The error spectrum chart. It shares a tab with multiple and partial
// coherence but is a different kind of picture — a power density in the
// target's units rather than a share — so the branch that separates them is
// worth pinning, along with the log axis, which is not a preference here: the
// unexplained curve is usually orders of magnitude below the signal, and on a
// linear axis the gap that *is* the answer collapses onto the x-axis.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildPlot } from '../../frontend/src/lib/plotSpec.js'
import { T } from './helpers.mjs'

const freqs = [0, 1, 2, 3, 4]

const errorResult = (extra = {}) => ({
  mode: 'error',
  freqs,
  target: 'x1_disp',
  predictors: ['force1', 'force2'],
  target_psd: [1e-3, 1e-2, 1e-1, 1e-2, 1e-3],
  error_spectrum: [1e-7, 1e-6, 1e-5, 1e-6, 1e-7],
  coherence: [0.9999, 0.9999, 0.9999, 0.9999, 0.9999],
  ordinary_coherence: [{ name: 'force1', values: [0.9, 0.9, 0.9, 0.9, 0.9] }],
  input_condition: [1, 1, 1, 1, 1],
  bias_floor: 0.051,
  n_segments: 39,
  unexplained_variance: 6.71e-9,
  unexplained_fraction: 0.000389,
  notes: [],
  ...extra,
})

const multipleResult = {
  mode: 'multiple',
  freqs,
  labels: ['a', 'b'],
  signals: [{ name: 'a', values: [0.1, 0.2, 0.3, 0.4, 0.5] },
            { name: 'b', values: [0.5, 0.4, 0.3, 0.2, 0.1] }],
}

const units = { signal: 'm', focus: 'm', byName: { x1_disp: 'm', force1: 'N' } }
const opts = (extra = {}) => ({ T, units, ...extra })

test('the error spectrum draws the target and the unexplained part together', () => {
  const spec = buildPlot('predictability', errorResult(), opts())
  assert.equal(spec.traces.length, 2)
  assert.equal(spec.traces[0].name, 'x1_disp — total')
  assert.equal(spec.traces[1].name, 'Unexplained')
  // The gap between them is the answer, so both must be on the same axis.
  assert.equal(spec.traces[0].yaxis ?? 'y', spec.traces[1].yaxis ?? 'y')
})

test('its y axis is a power density in the target unit, squared and per Hz', () => {
  const spec = buildPlot('predictability', errorResult(), opts())
  assert.equal(spec.layout.yaxis.title, 'PSD [m²/Hz]')
})

test('the target unit is taken from the target, not from a predictor', () => {
  // force1 is in newtons and is in the same selection. Reading the shared unit
  // rather than the named target's would put [N²/Hz] on a displacement axis.
  const spec = buildPlot('predictability', errorResult(),
                         { T, units: { signal: '', focus: 'N', byName: units.byName } })
  assert.equal(spec.layout.yaxis.title, 'PSD [m²/Hz]')
})

test('an undeclared target unit leaves the axis bare rather than guessing', () => {
  const spec = buildPlot('predictability', errorResult(), { T, units: {} })
  assert.equal(spec.layout.yaxis.title, 'PSD')
})

test('the axis is logarithmic whatever the y-log toggle says', () => {
  // Four decades separate the two curves in the fixture. A linear axis would
  // render the unexplained trace as a flat line on zero.
  for (const yLog of [true, false]) {
    const spec = buildPlot('predictability', errorResult(), opts({ yLog }))
    assert.equal(spec.layout.yaxis.type, 'log')
  }
})

test('the title carries the headline number and the floor it must be read against', () => {
  const title = buildPlot('predictability', errorResult(), opts()).layout.title.text
  assert.match(title, /x1_disp from force1 \+ force2/)
  assert.match(title, /0\.039% unexplained/)   // two significant figures below 1%
  assert.match(title, /bias floor 0\.051 over 39 segments/)
})

test('a large fraction is shown to one decimal, not to two significant figures', () => {
  const title = buildPlot('predictability',
                          errorResult({ unexplained_fraction: 0.389 }),
                          opts()).layout.title.text
  assert.match(title, /38\.9% unexplained/)
})

test('many predictors are counted rather than listed, to keep the title readable', () => {
  const d = errorResult({ predictors: ['a', 'b', 'c', 'd'] })
  assert.match(buildPlot('predictability', d, opts()).layout.title.text,
               /from 4 channels/)
})

test('the other two modes are untouched and still share the 0-1 axis', () => {
  const spec = buildPlot('predictability', multipleResult, opts())
  assert.equal(spec.traces.length, 2)
  assert.equal(spec.layout.yaxis.title, 'Coherence')
  assert.deepEqual(spec.layout.yaxis.range, [0, 1])
  assert.notEqual(spec.layout.yaxis.type, 'log')
})
