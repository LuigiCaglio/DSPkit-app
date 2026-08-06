// Explaining a rejected time column.
//
// When detection gives up, the app falls back to a typed-in sample rate. That
// fallback is fine; being quiet about it is not. A record with one dropped
// sample used to land on the default 1000 Hz and look completely normal, with
// every frequency axis wrong by whatever ratio that happened to be.
//
// The distinction that matters is between *one gap* and *genuine jitter*: the
// first still has a perfectly good sample rate sitting in the median interval,
// the second does not. `n_irregular` out of `n_intervals` is what separates
// them, so it leads every message here.
//
// Runes-free so the tests can import it under plain node.

/** Enough decimals to be useful, without pretending to precision. */
function fmtHz(hz) {
  if (!Number.isFinite(hz) || hz <= 0) return null
  if (hz >= 100) return `${hz.toFixed(1)} Hz`
  if (hz >= 1) return `${hz.toFixed(3)} Hz`
  return `${hz.toPrecision(3)} Hz`
}

/**
 * An interval in the largest unit that still reads as ≥ 1.
 *
 * The unit is chosen from the *rounded* value, not the raw one. A 1 ms interval
 * written out to nine decimals comes back as 0.000999999…, which a direct
 * `>= 1e-3` test puts in microseconds — so a spread of 1 ms to 2 ms rendered as
 * "1000 µs–2.000 ms", inviting the reader to compare two different units.
 */
function fmtDt(s) {
  if (!Number.isFinite(s)) return '?'
  const units = [[1, 's'], [1e-3, 'ms'], [1e-6, 'µs']]
  for (const [scale, name] of units) {
    const v = s / scale
    if (Number(v.toPrecision(4)) >= 1) return `${v.toPrecision(4)} ${name}`
  }
  return `${(s * 1e9).toPrecision(4)} ns`
}

/**
 * The sample rate implied by the median interval of a rejected column.
 *
 * Worth preferring over a hardcoded default even when detection refused the
 * column: it is derived from this file, and for the common single-dropout case
 * it is exactly right. Returned separately from the prose so the caller can
 * seed the manual field with it.
 */
export function impliedFs(rejection) {
  const fs = rejection?.implied_fs
  return Number.isFinite(fs) && fs > 0 ? fs : null
}

/**
 * A plain-language account of why no time column was used.
 *
 * Returns null when nothing came close to being a time column — that is the
 * ordinary "this file has no time axis" case, which needs no explanation.
 */
export function describeRejection(rejection, columnNames = []) {
  if (!rejection || typeof rejection !== 'object') return null
  const name = columnNames[rejection.col] ?? `column ${rejection.col}`
  const fs = impliedFs(rejection)
  const total = rejection.n_intervals
  const odd = rejection.n_irregular

  if (rejection.reason === 'not_monotonic') {
    const n = rejection.n_backwards ?? 0
    return {
      severity: 'warn',
      headline: `"${name}" goes backwards`,
      detail: `${n} of ${total ?? '?'} steps are zero or negative, so it can't be`
        + ` read as time. A clock reset or two files concatenated out of order`
        + ` would both look like this.`,
      impliedFs: fs,
    }
  }

  if (rejection.reason === 'non_uniform') {
    const spread = `intervals run ${fmtDt(rejection.min_dt)}–${fmtDt(rejection.max_dt)}`
      + `, median ${fmtDt(rejection.median_dt)}`
    // One or two odd intervals is a dropout: the median is still the true rate.
    if (odd != null && total && odd <= Math.max(2, total * 0.001)) {
      return {
        severity: 'info',
        headline: `"${name}" has ${odd === 1 ? 'a gap' : `${odd} gaps`}`,
        detail: `${odd} of ${total} intervals differ from the median; ${spread}.`
          + ` The rate between the gaps is steady, so ${fmtHz(fs) ?? 'the median'}`
          + ` is still the right sample rate — but the record is not continuous.`,
        impliedFs: fs,
      }
    }
    return {
      severity: 'warn',
      headline: `"${name}" is not evenly sampled`,
      detail: `${odd ?? 'many'} of ${total ?? '?'} intervals differ from the median;`
        + ` ${spread}. Spectral results assume a fixed rate, so treat anything`
        + ` frequency-domain from this record with suspicion until it is resampled.`,
      impliedFs: fs,
    }
  }

  return null
}
