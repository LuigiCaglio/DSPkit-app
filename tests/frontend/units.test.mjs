// A unit on an axis is a claim, and a wrong one is worse than none. These cover
// the two ways it goes wrong: the algebra (an acceleration PSD is (m/s²)²/Hz,
// not m/s²/Hz) and the honesty rule (say nothing when the channels disagree).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeUnit, squared, product, perHz, psdUnit, csdUnit, densityUnit,
  withUnit, commonUnit, resolveUnits, sanitizeUnits, UNIT_PRESETS,
} from '../../frontend/src/lib/units.js'

// ── cleaning input ───────────────────────────────────────────────────────────

test('a blank unit and a missing one are the same thing', () => {
  assert.equal(normalizeUnit(''), '')
  assert.equal(normalizeUnit('   '), '')
  assert.equal(normalizeUnit(undefined), '')
  assert.equal(normalizeUnit(null), '')
  assert.equal(normalizeUnit(42), '')
})

test('surrounding whitespace is not part of a unit', () => {
  assert.equal(normalizeUnit('  m/s²  '), 'm/s²')
})

test('a pasted paragraph cannot become a unit', () => {
  assert.equal(normalizeUnit('x'.repeat(200)).length, 16)
})

// ── the exponent bracketing, which is the whole point ────────────────────────

test('a compound unit is bracketed before it is squared', () => {
  assert.equal(squared('m/s²'), '(m/s²)²')
  assert.equal(squared('mm/s'), '(mm/s)²')
})

test('a simple unit takes the exponent directly', () => {
  assert.equal(squared('g'), 'g²')
  assert.equal(squared('V'), 'V²')
  assert.equal(squared('µε'), 'µε²')
})

test('squaring nothing is still nothing', () => {
  assert.equal(squared(''), '')
  assert.equal(squared(undefined), '')
})

test('an acceleration PSD is (m/s²)²/Hz — the case this exists for', () => {
  assert.equal(psdUnit('m/s²'), '(m/s²)²/Hz')
})

test('a PSD in g reads g²/Hz, as everyone writes it', () => {
  assert.equal(psdUnit('g'), 'g²/Hz')
})

test('an undeclared channel gets a bare PSD axis, not a stray /Hz', () => {
  assert.equal(psdUnit(''), '')
  assert.equal(perHz(''), '')
})

// ── two channels ─────────────────────────────────────────────────────────────

test('a cross-spectrum of matching units squares rather than repeating', () => {
  assert.equal(product('g', 'g'), 'g²')
  assert.equal(csdUnit('m/s²', 'm/s²'), '(m/s²)²/Hz')
})

test('a cross-spectrum of different units keeps both', () => {
  assert.equal(product('g', 'mm'), 'g·mm')
  assert.equal(csdUnit('N', 'mm'), 'N·mm/Hz')
})

test('one missing unit makes the product unknown, not half-known', () => {
  assert.equal(product('g', ''), '')
  assert.equal(product('', 'g'), '')
  assert.equal(csdUnit('m/s²', ''), '')
})

// ── densities ────────────────────────────────────────────────────────────────

test('a probability density is the reciprocal, bracketed when compound', () => {
  assert.equal(densityUnit('m/s²'), '1/(m/s²)')
  assert.equal(densityUnit('g'), '1/g')
  assert.equal(densityUnit(''), '')
})

// ── attaching to a label ─────────────────────────────────────────────────────

test('a known unit is bracketed onto the label', () => {
  assert.equal(withUnit('Amplitude', 'g'), 'Amplitude [g]')
})

test('an unknown unit leaves the label untouched', () => {
  assert.equal(withUnit('Amplitude', ''), 'Amplitude')
  assert.equal(withUnit('Amplitude', undefined), 'Amplitude')
})

// ── the honesty rule ─────────────────────────────────────────────────────────

test('channels that agree share their unit', () => {
  assert.equal(commonUnit({ 0: 'g', 1: 'g', 2: 'mm' }, [0, 1]), 'g')
})

test('channels that disagree produce no unit at all', () => {
  // The failure this prevents: labelling a two-channel overlay 'g' because the
  // first channel happens to be in g.
  assert.equal(commonUnit({ 0: 'g', 1: 'mm' }, [0, 1]), '')
})

test('one undeclared channel is enough to silence the axis', () => {
  assert.equal(commonUnit({ 0: 'g' }, [0, 1]), '')
  assert.equal(commonUnit({ 0: 'g', 1: '' }, [0, 1]), '')
})

test('no selection and no map are both simply unknown', () => {
  assert.equal(commonUnit({ 0: 'g' }, []), '')
  assert.equal(commonUnit(null, [0]), '')
})

test('a single declared channel does carry its unit', () => {
  assert.equal(commonUnit({ 3: 'kN' }, [3]), 'kN')
})

// ── what the charts are handed ───────────────────────────────────────────────

test('resolveUnits gives the overlay unit, the pair units and a name map', () => {
  const u = resolveUnits(
    { 1: 'g', 2: 'g', 3: 'mm' },
    [1, 2],
    { x: 1, y: 3 },
    ['t', 'acc1', 'acc2', 'disp'],
  )
  assert.equal(u.signal, 'g')       // the two selected agree
  assert.equal(u.x, 'g')
  assert.equal(u.y, 'mm')           // pair axes are per-channel, so they differ
  assert.deepEqual(u.byName, { acc1: 'g', acc2: 'g', disp: 'mm' })
})

test('a grid cell can still be labelled when the shared axis cannot', () => {
  // Mixed units silence the overlay, but each small-multiple cell shows one
  // channel and stays labellable — that asymmetry is the point of byName.
  const u = resolveUnits({ 0: 'g', 1: 'mm' }, [0, 1], {}, ['a', 'b'])
  assert.equal(u.signal, '')
  assert.equal(u.byName.a, 'g')
  assert.equal(u.byName.b, 'mm')
})

test('undeclared channels are absent from the name map, not empty in it', () => {
  const u = resolveUnits({ 0: 'g' }, [0], {}, ['a', 'b'])
  assert.deepEqual(u.byName, { a: 'g' })
})

// ── what survives a reload ───────────────────────────────────────────────────

test('units past the end of the file are dropped', () => {
  // Same distrust applyState applies to a restored channel selection.
  assert.deepEqual(sanitizeUnits({ 0: 'g', 5: 'mm' }, 3), { 0: 'g' })
})

test('blank and junk entries do not survive', () => {
  assert.deepEqual(sanitizeUnits({ 0: 'g', 1: '  ', 2: null, x: 'mm' }, 4), { 0: 'g' })
})

test('a nonsense map or column count yields an empty map', () => {
  assert.deepEqual(sanitizeUnits(null, 3), {})
  assert.deepEqual(sanitizeUnits([1, 2], 3), {})
  assert.deepEqual(sanitizeUnits({ 0: 'g' }, 0), {})
  assert.deepEqual(sanitizeUnits({ 0: 'g' }, undefined), {})
})

test('every preset survives its own cleaning and squares legibly', () => {
  for (const p of UNIT_PRESETS) {
    assert.equal(normalizeUnit(p), p, `${p} should be stored as typed`)
    assert.ok(squared(p).endsWith('²'), `${p} should square`)
    assert.ok(psdUnit(p).endsWith('/Hz'), `${p} should give a density`)
  }
})

test('JSON string keys are what actually arrive from the backend', () => {
  // A stored blob round-trips through JSON, so `{1: 'g'}` comes back as
  // `{"1": "g"}`. Verified against a live backend; pinned here so a rewrite of
  // sanitizeUnits cannot quietly start rejecting the real wire format.
  const fromWire = JSON.parse('{"1":"mm","2":"mm","9":"g"}')
  const clean = sanitizeUnits(fromWire, 5)
  assert.deepEqual(clean, { 1: 'mm', 2: 'mm' })
  assert.equal(commonUnit(clean, [1, 2]), 'mm')
})

test('a comma in a unit cannot break a CSV header', () => {
  assert.equal(normalizeUnit('m,s'), 'ms')
  assert.equal(normalizeUnit('a"b'), 'ab')
})
