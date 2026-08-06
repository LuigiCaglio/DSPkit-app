// A rejected time column must say which kind of rejection it was. The whole
// point is separating "one dropped sample, the rate is still 1000 Hz" from
// "this record is genuinely irregular, don't trust any spectrum from it" --
// both used to land silently on a hardcoded 1000 Hz that looked entirely normal.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeRejection, impliedFs } from '../../frontend/src/lib/detect.js'

const NAMES = ['t', 'x1', 'x2']

const dropout = {
  col: 0,
  reason: 'non_uniform',
  median_dt: 0.001,
  min_dt: 0.001,
  max_dt: 0.002,
  cv: 0.0141,
  n_irregular: 1,
  n_intervals: 4999,
  implied_fs: 1000,
}

const jitter = {
  col: 0,
  reason: 'non_uniform',
  median_dt: 0.0010009,
  min_dt: 0.0008,
  max_dt: 0.0011948,
  cv: 0.05,
  n_irregular: 4212,
  n_intervals: 4999,
  implied_fs: 999.1,
}

const backwards = {
  col: 0,
  reason: 'not_monotonic',
  n_backwards: 1,
  n_intervals: 4998,
  median_dt: 0.001,
  min_dt: 0.001,
  max_dt: 1.001,
  implied_fs: 1000,
}

test('no near-miss produces no explanation', () => {
  // A file that simply has no time axis needs no story told about it.
  assert.equal(describeRejection(null, NAMES), null)
  assert.equal(describeRejection(undefined, NAMES), null)
  assert.equal(describeRejection({ reason: 'something-else' }, NAMES), null)
})

test('a single dropout is reported as a gap, not as bad data', () => {
  const d = describeRejection(dropout, NAMES)
  assert.equal(d.severity, 'info', 'one gap does not invalidate the sample rate')
  assert.match(d.headline, /gap/)
  assert.match(d.headline, /"t"/, 'the offending column is named')
  assert.match(d.detail, /1 of 4999/)
  assert.match(d.detail, /1000\.0 Hz/, 'the usable rate is stated outright')
  assert.match(d.detail, /not continuous/, 'the gap itself is still called out')
})

test('pervasive jitter is a warning, and says spectra are suspect', () => {
  const d = describeRejection(jitter, NAMES)
  assert.equal(d.severity, 'warn')
  assert.match(d.headline, /not evenly sampled/)
  assert.match(d.detail, /4212 of 4999/)
  assert.match(d.detail, /suspicion|resampled/)
})

test('the gap and jitter cases are told apart by count, not by cv', () => {
  // Both have a cv well over the threshold; only the proportion of irregular
  // intervals distinguishes a dropout from genuine jitter.
  assert.ok(dropout.cv > 0.001 && jitter.cv > 0.001)
  assert.notEqual(describeRejection(dropout, NAMES).severity,
                  describeRejection(jitter, NAMES).severity)
})

test('a couple of gaps in a long record still counts as gaps', () => {
  const d = describeRejection({ ...dropout, n_irregular: 2 }, NAMES)
  assert.equal(d.severity, 'info')
  assert.match(d.headline, /2 gaps/)
})

test('a handful of gaps in a short record is not treated as one dropout', () => {
  const d = describeRejection(
    { ...dropout, n_irregular: 3, n_intervals: 40 }, NAMES)
  assert.equal(d.severity, 'warn')
})

test('a column running backwards is named as such', () => {
  const d = describeRejection(backwards, NAMES)
  assert.equal(d.severity, 'warn')
  assert.match(d.headline, /backwards/)
  assert.match(d.detail, /1 of 4998/)
  assert.match(d.detail, /clock reset|out of order/)
})

test('a column with no name falls back to its index', () => {
  assert.match(describeRejection(dropout, []).headline, /column 0/)
})

test('intervals are shown in units a person reads, not raw seconds', () => {
  assert.match(describeRejection(dropout, NAMES).detail, /ms/)
  const slow = { ...dropout, median_dt: 2, min_dt: 2, max_dt: 4, implied_fs: 0.5 }
  assert.match(describeRejection(slow, NAMES).detail, /\ss\b/)
  const fast = { ...dropout, median_dt: 2e-6, min_dt: 2e-6, max_dt: 4e-6, implied_fs: 500000 }
  assert.match(describeRejection(fast, NAMES).detail, /µs/)
})

test('one spread is quoted in one unit, whatever float error did to it', () => {
  // A 1 ms interval written to nine decimals reads back as 0.000999999…, which
  // a direct threshold test drops into microseconds -- rendering a 1-to-2 ms
  // spread as "1000 µs–2.000 ms" and inviting a comparison across units.
  const wobbly = {
    ...dropout,
    min_dt: 0.0009999999999998899,
    median_dt: 0.0009999999999998899,
    max_dt: 0.002000000000000668,
  }
  const detail = describeRejection(wobbly, NAMES).detail
  const spread = detail.match(/intervals run ([^,]*)/)[1]
  assert.match(spread, /1\.000 ms–2\.000 ms/, spread)
  assert.ok(!spread.includes('µs'), `mixed units: ${spread}`)
})

test('the implied rate is offered only when it is usable', () => {
  assert.equal(impliedFs(dropout), 1000)
  assert.equal(impliedFs({ ...dropout, implied_fs: 0 }), null)
  assert.equal(impliedFs({ ...dropout, implied_fs: null }), null)
  assert.equal(impliedFs({ ...dropout, implied_fs: -3 }), null)
  assert.equal(impliedFs(null), null)
})
