// An FDD mode table is unreadable without the bar its rows had to clear, and
// with real thresholds an empty table is now a legitimate answer rather than a
// broken panel. Both have to be stated.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeCriteria, describeEmpty, dominanceLabel }
  from '../../frontend/src/lib/fdd.js'

const accepted = {
  prominence_db: 6,
  min_dominance_db: 6,
  max_peaks: 10,
  defaulted: true,
  n_candidates: 119,
  n_accepted: 2,
}

const rejectedAll = { ...accepted, n_accepted: 0, n_candidates: 141 }

test('the criteria line states both thresholds and the survival count', () => {
  const s = describeCriteria(accepted)
  assert.match(s, /2 of 119/)
  assert.match(s, /prominence ≥ 6 dB/)
  assert.match(s, /SV1\/SV2 ≥ 6 dB/)
})

test('defaults and user settings are distinguishable', () => {
  assert.match(describeCriteria(accepted), /defaults/)
  assert.match(describeCriteria({ ...accepted, defaulted: false }), /your settings/)
})

test('a disabled dominance gate is not claimed as active', () => {
  const s = describeCriteria({ ...accepted, min_dominance_db: 0 })
  assert.doesNotMatch(s, /SV1\/SV2/)
  assert.match(s, /prominence ≥ 6 dB/)
})

test('a response from before criteria existed degrades quietly', () => {
  assert.equal(describeCriteria(undefined), null)
  assert.equal(describeCriteria(null), null)
  assert.equal(describeEmpty(undefined), null)
})

test('nothing to explain when peaks were accepted', () => {
  assert.equal(describeEmpty(accepted, ['x1', 'x2']), null)
})

test('an empty result names the bar and the usual cause', () => {
  const e = describeEmpty(rejectedAll, ['x1', 'x2', 'force1'])
  assert.match(e.headline, /No candidate peak met/)
  assert.match(e.detail, /141/)
  assert.match(e.detail, /6 dB prominence/)
  assert.match(e.detail, /SV1\/SV2/)
  assert.match(e.detail, /excitation/, 'the force-channel trap is the usual cause')
  assert.match(e.detail, /Lower the thresholds/, 'and it says how to look anyway')
})

test('no local maxima at all is a different message from none qualifying', () => {
  const none = describeEmpty({ ...rejectedAll, n_candidates: 0 })
  assert.match(none.headline, /No peaks in the singular-value curve/)
  assert.match(none.detail, /nperseg/)
  assert.notEqual(none.headline, describeEmpty(rejectedAll).headline)
})

test('the empty message works with no channel labels', () => {
  const e = describeEmpty(rejectedAll, [])
  assert.ok(e.detail.length > 0)
  assert.match(e.detail, /excitation channel is included/)
})

test('dominance is labelled coarsely, so 6 dB and 40 dB do not read alike', () => {
  assert.equal(dominanceLabel(38.1), 'strong')
  assert.equal(dominanceLabel(25.4), 'strong')
  assert.equal(dominanceLabel(12), 'clear')
  assert.equal(dominanceLabel(6.5), 'marginal')
  assert.equal(dominanceLabel(NaN), '')
  assert.equal(dominanceLabel(undefined), '')
})
