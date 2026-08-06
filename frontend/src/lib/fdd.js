// Saying what an FDD mode table is, and isn't.
//
// Every peak FDD returns arrives with a damping ratio and a mode shape, so it
// reads as a result whether or not it is one. The picker used to apply no
// prominence filter at all and simply return the ten most prominent local
// maxima, which on a clean two-mode record meant two real modes and eight
// pieces of noise, identical in the table.
//
// With real thresholds, the failure mode inverts: a table can now legitimately
// come back empty. That has to read as "nothing here met the bar", with the bar
// stated, rather than as a broken panel — so the criteria travel with the
// result and get rendered either way.
//
// Runes-free so the tests can import it under plain node.

/**
 * One line stating what was required and how much survived.
 * Returns null for a response from before criteria were reported.
 */
export function describeCriteria(criteria) {
  if (!criteria || typeof criteria !== 'object') return null
  const bits = [`prominence ≥ ${criteria.prominence_db} dB`]
  if (criteria.min_dominance_db > 0) {
    bits.push(`SV1/SV2 ≥ ${criteria.min_dominance_db} dB`)
  }
  const accepted = criteria.n_accepted ?? 0
  const candidates = criteria.n_candidates ?? 0
  return `${accepted} of ${candidates} candidate peak${candidates === 1 ? '' : 's'}`
    + ` met ${bits.join(' and ')}`
    + (criteria.defaulted ? ' (defaults)' : ' (your settings)')
}

/**
 * What to show instead of a mode table when nothing qualified.
 *
 * An empty FDD result is a real, informative answer — most often it means the
 * selection includes excitation channels, where FDD has no meaning at all. It
 * should never look like a failure, and it should say what to change.
 */
export function describeEmpty(criteria, labels = []) {
  if (!criteria) return null
  if ((criteria.n_accepted ?? 0) > 0) return null
  const candidates = criteria.n_candidates ?? 0

  if (candidates === 0) {
    return {
      headline: 'No peaks in the singular-value curve',
      detail: 'The first singular value has no local maxima to test. Check that'
        + ' the record is long enough for the chosen nperseg.',
    }
  }
  return {
    headline: 'No candidate peak met the criteria',
    detail: `All ${candidates} local maxima in the SV1 curve fell below`
      + ` ${criteria.prominence_db} dB prominence`
      + (criteria.min_dominance_db > 0
        ? ` or ${criteria.min_dominance_db} dB SV1/SV2 dominance`
        : '')
      + '. That usually means there are no clear modes in this selection —'
      + (labels.length
        ? ` most often because ${labels.length === 1 ? 'the channel is' : 'one of '
          + labels.join(', ') + ' is'} an excitation input rather than a response.`
        : ' most often because an excitation channel is included.')
      + ' Lower the thresholds to see the rejected peaks.',
  }
}

/**
 * How confidently a peak reads as a mode, from its SV1/SV2 separation.
 *
 * Deliberately coarse. The number is what matters; this only keeps the reader
 * from treating a 6.1 dB peak and a 40 dB peak as equally solid.
 */
export function dominanceLabel(db) {
  if (!Number.isFinite(db)) return ''
  if (db >= 20) return 'strong'
  if (db >= 10) return 'clear'
  return 'marginal'
}
