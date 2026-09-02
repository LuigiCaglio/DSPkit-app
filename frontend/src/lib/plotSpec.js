// Pure chart builders: (tab, data, opts) -> { traces, layout } for Plotly.react().
//
// These live outside PlotPanel so one analysis has exactly one chart definition,
// renderable into the main canvas, a small-multiples grid cell, or an Overview
// panel. Nothing here touches the DOM or component state.

import { withUnit, psdUnit, csdUnit, densityUnit, squared, product,
         commonUnitByName } from './units.js'

export const MAX_PLOT_POINTS = 50_000

/** First index with x[i] >= v, assuming x ascending. */
function lowerBound(x, v) {
  let lo = 0, hi = x.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (x[mid] < v) lo = mid + 1; else hi = mid
  }
  return lo
}

/**
 * Thin out a series for display only; the exported CSV keeps every sample.
 *
 * When `range` is given the series is windowed to it *before* decimating, so
 * zooming in spends the whole point budget on what is actually on screen — a
 * 20x zoom shows 20x the detail, up to the raw sample rate. The alternative
 * (decimate once, then let the viewer zoom) turns a smooth curve into steps.
 */
export function downsampleXY(x, y, enabled = true, range = null) {
  if (!x || x.length === 0) return { x, y }

  let lo = 0, hi = x.length - 1
  if (range) {
    // One sample of margin each side so the curve reaches the viewport edges.
    lo = Math.max(0, lowerBound(x, range[0]) - 1)
    hi = Math.min(x.length - 1, lowerBound(x, range[1]) + 1)
    if (hi < lo) return { x: [], y: [] }
  }

  const n = hi - lo + 1
  if (!enabled || n <= MAX_PLOT_POINTS) {
    return range ? { x: x.slice(lo, hi + 1), y: y.slice(lo, hi + 1) } : { x, y }
  }
  const step = Math.ceil(n / MAX_PLOT_POINTS)
  const xd = [], yd = []
  for (let i = lo; i <= hi; i += step) { xd.push(x[i]); yd.push(y[i]) }
  return { x: xd, y: yd }
}

/** True when `tab`'s payload is long enough that display downsampling kicks in. */
export function isDownsampledFor(tab, d) {
  if (!d) return false
  if (tab === 'timeseries')
    return d.times_raw?.length > MAX_PLOT_POINTS || d.times_proc?.length > MAX_PLOT_POINTS
  if (tab === 'filter' || tab === 'instantaneous')
    return d.times?.length > MAX_PLOT_POINTS
  return false
}

/**
 * Perceptually uniform sequential ramps only.
 *
 * A spectrogram encodes magnitude, so the colour must be monotonic in lightness
 * — jet/turbo/rainbow invent bands of contrast where the data has none and are
 * unreadable with colour-vision deficiency. All four below are monotonic and
 * CVD-safe; Cividis is additionally optimised for it.
 */
/**
 * Tabs whose y quantity is strictly positive, and may therefore be log-scaled.
 * PSD is here too, though it carries its own `psdYLog` flag with its own default.
 * Everything absent is signed (waveforms, ACF/CCF, IMFs, covariance, dB values)
 * or bounded (coherence), and must never get a log axis.
 */
export const LOG_Y_TABS = new Set(['fft', 'psd', 'peaks', 'envelope'])

export const HEATMAP_SCALES = ['Viridis', 'Cividis', 'Magma', 'Inferno']

/**
 * Thin a 2-D grid for a 3-D surface.
 *
 * A spectrogram is routinely hundreds of frequency bins by thousands of frames.
 * A heatmap draws that as an image and does not care; a surface has to build a
 * mesh, and hundreds of thousands of vertices makes the view unusable to rotate
 * for a picture that a thinned grid draws identically.
 */
const SURFACE_MAX = 160

function thinSurface(x, y, z) {
  const sx = Math.max(1, Math.ceil(x.length / SURFACE_MAX))
  const sy = Math.max(1, Math.ceil(y.length / SURFACE_MAX))
  if (sx === 1 && sy === 1) return { x, y, z }
  const xi = x.filter((_, i) => i % sx === 0)
  const yi = y.filter((_, i) => i % sy === 0)
  const zi = z.filter((_, r) => r % sy === 0).map(row => row.filter((_, c) => c % sx === 0))
  return { x: xi, y: yi, z: zi }
}

/** Largest |value| in a 2-D array, ignoring non-finite entries. */
function peakAbs(z) {
  let peak = 0
  for (const row of z) {
    for (const v of row) {
      const a = Math.abs(v)
      if (Number.isFinite(a) && a > peak) peak = a
    }
  }
  return peak
}

/** Percentile over a flattened 2-D array, ignoring non-finite entries. */
function percentileOf(z, p) {
  const flat = []
  for (const row of z) for (const v of row) if (Number.isFinite(v)) flat.push(v)
  if (!flat.length) return null
  flat.sort((a, b) => a - b)
  const i = Math.min(flat.length - 1, Math.max(0, Math.round((p / 100) * (flat.length - 1))))
  return flat[i]
}

/**
 * Convert a time-frequency distribution to dB relative to its own peak.
 *
 * WVD and SPWVD are quasi-probability distributions and go negative, so the
 * magnitude is taken first — a raw log of those arrays produces NaN holes.
 * Values below the floor are clamped rather than left as -Infinity, which
 * Plotly renders as gaps.
 */
export function toDecibels(z, floorDb) {
  const peak = peakAbs(z)
  if (!(peak > 0)) return { z, zmin: undefined, zmax: undefined }
  const floor = -Math.abs(floorDb)
  const out = z.map(row => row.map(v => {
    const a = Math.abs(v) / peak
    if (!(a > 0)) return floor
    const db = 20 * Math.log10(a)
    return db < floor ? floor : db
  }))
  return { z: out, zmin: floor, zmax: 0 }
}

function baseLayout(T, cell = false) {
  return {
    paper_bgcolor: T.paper,
    plot_bgcolor:  T.bg,
    font:          { color: T.text, size: cell ? 10 : 12 },
    margin:        cell ? { l: 46, r: 12, t: 26, b: 36 } : { l: 60, r: 20, t: 30, b: 50 },
    // automargin lets Plotly grow the margin to fit tick labels and the axis
    // title. Without it the fixed bottom margin clips the title on a short
    // plot -- "Lag [s]" simply vanished, leaving bare numbers.
    xaxis:         { gridcolor: T.grid, zerolinecolor: T.grid, automargin: true },
    yaxis:         { gridcolor: T.grid, zerolinecolor: T.grid, automargin: true },
    // A legend is always shown for >= 2 series so identity is never colour-alone.
    legend:        { bgcolor: T.legend, bordercolor: T.border, borderwidth: 1 },
  }
}

function merge(...objs) { return Object.assign({}, ...objs) }

/**
 * Build the Plotly spec for one analysis.
 *
 * @param tab   analysis id (matches App's tab ids)
 * @param d     the endpoint payload
 * @param opts  {T, colors, normalize, yLog, psd, downsample, cell, title}
 * @returns {{traces: Array, layout: Object}|null}
 */
export function buildPlot(tab, d, opts) {
  const {
    T,
    colors = T.series,
    normalize = false,
    yLog = false,
    psd = {},
    downsample: dsOn = true,
    cell = false,
    title = null,
    xRange = null,
    lagSide = 'both',        // 'both' | 'positive' | 'negative'
    band = null,             // {hp, lp} — the pass band currently in force
    dragmode = null,         // 'select' puts the plot in band-picking mode
    response = null,         // {freqs, magnitude} — the filter's own response
    tf = {},                 // heatmap scaling: {db, rangeDb, clipPct, colorscale}
    units = {},              // resolved by units.js: {signal, x, y, byName}
    rsQuantity = 'PSa',      // response spectrum: which quantity to draw
    rdtNormalize = true,     // random decrement: compare shapes, not amplitudes
    showHist = true,         // distributions: draw the histogram bars
    showKde = true,          // distributions: draw the smooth density
  } = opts

  const L = baseLayout(T, cell)
  // A log axis is only meaningful for a strictly positive quantity. Plotly
  // silently DROPS every non-positive sample on a log axis, so applying it to a
  // waveform -- which oscillates about zero -- deletes half the data and says
  // nothing. Gating here rather than at the toggle closes the single-chart,
  // grid and Overview paths at once, since all three come through this function.
  const yType = (yLog && LOG_Y_TABS.has(tab)) ? 'log' : 'linear'

  // The channel unit this chart may label its amplitude axis with.
  //
  // Two things suppress it. Normalising divides by RMS, which leaves a
  // dimensionless ratio — the axis already says "(norm.)" and a unit next to it
  // would be false. And in a small-multiples cell the shared unit may be empty
  // because the selection is mixed, while this one cell shows a single channel
  // whose unit is known; `byName` recovers it.
  const cellUnit = cell && title ? units.byName?.[title] : undefined
  const sigUnit  = normalize ? '' : (cellUnit ?? units.signal ?? '')
  // The one-channel analyses (filter, EMD, envelopes, distributions) run on the
  // focus channel, so a mixed selection does not make their unit unknown.
  const oneUnit  = cellUnit ?? units.focus ?? ''

  /** 'Amplitude' → 'Amplitude [g]', or unchanged when the unit is unknown. */
  const ampTitle = (label = 'Amplitude') =>
    withUnit(normalize ? `${label} (norm.)` : label, sigUnit)

  // Re-drawing at a finer resolution must not throw away the zoom that asked
  // for it, so the axis range is pinned whenever a window is active.
  const xAxisRange = xRange
    ? { range: [...xRange], autorange: false }
    : { autorange: true }

  const norm = (arr) => {
    if (!normalize) return arr
    const rms = Math.sqrt(arr.reduce((s, v) => s + v * v, 0) / arr.length)
    return rms > 0 ? arr.map(v => v / rms) : arr
  }
  const ds = (x, y) => downsampleXY(x, y, dsOn, xRange)

  const line = (x, y, name, dash = 'solid', yaxis = 'y', color = undefined) => ({
    x, y, type: 'scatter', mode: 'lines', name,
    line: { dash, ...(color ? { color } : {}) }, yaxis,
  })

  /**
   * A time-frequency surface.
   *
   * Linear magnitude is the wrong default here: real vibration data spans
   * several decades, so one bright ridge saturates the ramp and everything else
   * collapses to the bottom colour — the chart reads as a black rectangle with
   * a streak. dB relative to the peak, with an explicit dynamic range, is what
   * makes the structure visible.
   */
  /**
   * Axis titles for a time-frequency view.
   *
   * A 3-D surface puts its axes inside `scene` rather than at the top level, so
   * the tab branches ask for them here instead of writing xaxis/yaxis directly.
   */
  const tfAxes = () => tf.surface3d
    ? { scene: {
          xaxis: { title: { text: 'Time [s]' }, gridcolor: T.grid },
          yaxis: { title: { text: 'Frequency [Hz]' }, gridcolor: T.grid },
          zaxis: { title: { text: tf.db ? 'dB re peak' : 'Magnitude' }, gridcolor: T.grid },
          camera: { eye: { x: 1.5, y: -1.6, z: 0.9 } },
        } }
    : { xaxis: { ...L.xaxis, title: 'Time [s]' },
        yaxis: { ...L.yaxis, title: 'Frequency [Hz]' } }

  const heatmap = (x, y, z, { carriesSignalUnit = false } = {}) => {
    const { db = true, rangeDb = 60, clipPct = 99, colorscale = 'Viridis' } = tf
    let zz = z, zmin, zmax, unit

    if (db) {
      ({ z: zz, zmin, zmax } = toDecibels(z, rangeDb))
      unit = 'dB re peak'
    } else {
      // Clip the top percentile so a few outliers cannot own the whole ramp.
      const hi = percentileOf(z, clipPct)
      const lo = percentileOf(z, 0)
      if (hi != null && lo != null && hi > lo) { zmin = lo; zmax = hi }
      // STFT and CWT magnitudes carry the signal's own unit. WVD and SPWVD are
      // energy densities whose scaling makes the unit ambiguous, so they stay
      // bare rather than claim one.
      unit = carriesSignalUnit ? withUnit('magnitude', oneUnit) : 'magnitude'
    }

    const bar = {
      thickness: cell ? 10 : 14, outlinewidth: 0,
      title: { text: unit, side: 'right', font: { size: cell ? 9 : 11 } },
    }

    if (tf.surface3d) {
      const t = thinSurface(x, y, zz)
      return [{
        x: t.x, y: t.y, z: t.z, type: 'surface', colorscale,
        ...(zmin != null ? { cmin: zmin, cmax: zmax, cauto: false } : {}),
        colorbar: bar,
        contours: { z: { show: false } },
        hovertemplate: `%{x:.4g} s, %{y:.4g} Hz — %{z:.3g} ${db ? 'dB' : ''}<extra></extra>`,
      }]
    }

    return [{
      x, y, z: zz, type: 'heatmap', colorscale,
      ...(zmin != null ? { zmin, zmax, zauto: false } : {}),
      colorbar: bar,
      hovertemplate: `%{x:.4g} s, %{y:.4g} Hz — %{z:.3g} ${db ? 'dB' : ''}<extra></extra>`,
    }]
  }

  /** Shade what the filter removes, against the spectrum it was chosen from. */
  const bandShapes = (freqs) => {
    if (!band || (!band.hp && !band.lp)) return {}
    const reject = (x0, x1) => ({
      type: 'rect', xref: 'x', yref: 'paper', x0, x1, y0: 0, y1: 1,
      fillcolor: T.danger, opacity: 0.10, line: { width: 0 }, layer: 'below',
    })
    const shapes = []
    if (band.hp) shapes.push(reject(freqs[0], band.hp))
    if (band.lp) shapes.push(reject(band.lp, freqs[freqs.length - 1]))
    return shapes.length ? { shapes } : {}
  }

  // 'select' with a horizontal-only rectangle is the band-picking gesture; the
  // default drag zooms, which is not a selection and gave no visible feedback.
  const dragOpts = dragmode
    ? { dragmode, selectdirection: 'h' }
    : {}

  /**
   * The filter's magnitude response, on its own right-hand axis.
   *
   * The shaded band says which side is cut; this says *how sharply*, which is
   * the part you cannot guess from an order number — especially under
   * zero-phase filtering, where the real -3 dB point sits inside the cutoff.
   */
  const responseTrace = () => {
    if (!response?.freqs?.length) return null
    return {
      trace: {
        x: response.freqs, y: response.magnitude,
        type: 'scatter', mode: 'lines', name: 'filter response',
        yaxis: 'y2', hovertemplate: '%{x:.4g} Hz — gain %{y:.3f}<extra></extra>',
        line: { color: T.danger, width: 1.5, dash: 'dot' },
      },
      axis: {
        yaxis2: {
          title: 'Filter gain', overlaying: 'y', side: 'right',
          range: [0, 1.05], showgrid: false,
          gridcolor: T.grid, zerolinecolor: T.grid,
        },
      },
    }
  }

  /** Cell charts carry their channel name as the title; the main canvas may not. */
  const titled = (extra = {}) => title
    ? merge(extra, { title: { text: title, font: { color: T.title, size: cell ? 11 : 13 } } })
    : extra

  if (!d) return null

  if (tab === 'timeseries') {
    const traces = []
    d.signals.forEach((sig, i) => {
      const color = colors[i % colors.length]
      if (d.preprocessed) {
        const dr = ds(d.times_raw, norm(sig.signal_raw))
        traces.push({ x: dr.x, y: dr.y, type: 'scatter', mode: 'lines',
                      name: `${sig.name} (raw)`, opacity: 0.35, line: { color, dash: 'dot' } })
        const dp = ds(d.times_proc, norm(sig.signal_proc))
        traces.push({ x: dp.x, y: dp.y, type: 'scatter', mode: 'lines',
                      name: sig.name, line: { color } })
      } else {
        const dd = ds(d.times_raw, norm(sig.signal_raw))
        traces.push({ x: dd.x, y: dd.y, type: 'scatter', mode: 'lines',
                      name: sig.name, line: { color } })
      }
    })
    const dsLabel = isDownsampledFor(tab, d) && dsOn && !xRange ? '  (downsampled for display)' : ''
    const heading = title ?? `${d.n_proc.toLocaleString()} samples  ·  fs = ${d.fs_proc.toFixed(2)} Hz${dsLabel}`
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Time [s]', ...xAxisRange },
      yaxis: { ...L.yaxis, title: ampTitle(), type: yType },
      title: { text: heading, font: { color: T.text, size: 11 } },
    })}
  }

  if (tab === 'fft') {
    const traces = d.signals.map((sig, i) =>
      line(d.freqs, norm(sig.amplitude), sig.name, 'solid', 'y', colors[i % colors.length]))
    const rf = responseTrace()
    if (rf) traces.push(rf.trace)
    return { traces, layout: merge(L, titled({
      ...bandShapes(d.freqs),
      ...dragOpts,
      ...(rf ? rf.axis : {}),
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: ampTitle(), type: yType },
    }))}
  }

  if (tab === 'psd') {
    const traces = d.signals.map((sig, i) =>
      line(d.freqs, norm(sig.Pxx), sig.name, 'solid', 'y', colors[i % colors.length]))
    const rp = responseTrace()
    if (rp) traces.push(rp.trace)
    const xr = (psd.xMin !== '' && psd.xMin != null && psd.xMax !== '' && psd.xMax != null)
      ? [parseFloat(psd.xMin), parseFloat(psd.xMax)] : undefined
    const yr = (psd.yMin !== '' && psd.yMin != null && psd.yMax !== '' && psd.yMax != null)
      ? [parseFloat(psd.yMin), parseFloat(psd.yMax)] : undefined

    return { traces, layout: merge(L, titled({
      ...bandShapes(d.freqs),
      ...dragOpts,
      ...(rp ? rp.axis : {}),
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]',
               ...(xr ? { range: xr, autorange: false } : { autorange: true }) },
      yaxis: { ...L.yaxis, title: withUnit('PSD', psdUnit(sigUnit)), type: (psd.yLog ?? true) ? 'log' : 'linear',
               ...(yr ? { range: yr, autorange: false } : { autorange: true }) },
    }))}
  }

  if (tab === 'autocorrelation') {
    const traces = d.signals.map((sig, i) =>
      line(d.lags, sig.acf, sig.name, 'solid', 'y', colors[i % colors.length]))
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Lag [s]' },
      // A normalized ACF is a dimensionless ratio; a raw one is in the signal's
      // unit squared. The payload says which, so the axis does not have to guess.
      yaxis: { ...L.yaxis, title: withUnit('ACF', d.normalized === false ? squared(sigUnit) : '') },
    }))}
  }

  if (tab === 'cross_correlation') {
    // Lag sign carries the lead/lag direction, so which half you look at is a
    // question you ask constantly. Restrict the view rather than the data, so
    // switching sides costs nothing and the peak markers stay comparable.
    const loLag = d.lags[0]
    const hiLag = d.lags[d.lags.length - 1]
    const lagRange =
      lagSide === 'positive' ? [0, hiLag] :
      lagSide === 'negative' ? [loLag, 0] : null

    const traces = [line(d.lags, d.ccf, 'CCF', 'solid', 'y', colors[0])]

    // Where the strongest correlation sits within the visible half — the number
    // you actually want off this chart.
    let peakLag = null, peakVal = null
    for (let i = 0; i < d.lags.length; i++) {
      if (lagRange && (d.lags[i] < lagRange[0] || d.lags[i] > lagRange[1])) continue
      if (peakVal === null || Math.abs(d.ccf[i]) > Math.abs(peakVal)) {
        peakVal = d.ccf[i]; peakLag = d.lags[i]
      }
    }
    if (peakLag !== null) {
      traces.push({
        x: [peakLag], y: [peakVal], type: 'scatter', mode: 'markers',
        name: `peak ${peakLag.toPrecision(4)} s`,
        marker: { symbol: 'circle-open', size: cell ? 9 : 13, line: { width: 2 }, color: T.danger },
      })
    }

    // Say which channel leads, rather than leaving the sign convention to be
    // recalled. CCF[k] = sum x[n]*y[n+k], so a peak at positive lag means y is
    // the delayed copy and x arrives first.
    const lead = (() => {
      if (peakLag === null || !d.x_label || !d.y_label) return ''
      if (Math.abs(peakLag) < 1e-12) return '  ·  in phase, no lead'
      return peakLag > 0
        ? `  ·  ${d.x_label} leads ${d.y_label}`
        : `  ·  ${d.y_label} leads ${d.x_label}`
    })()
    const head = title ?? (peakLag !== null
      ? `Peak |CCF| ${peakVal.toPrecision(3)} at lag ${peakLag.toPrecision(4)} s${lead}`
      : null)

    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Lag [s]',
               ...(lagRange ? { range: lagRange, autorange: false } : { autorange: true }) },
      yaxis: { ...L.yaxis,
               title: withUnit('CCF', d.normalized === false ? product(units.x, units.y) : '') },
      ...(head ? { title: { text: head, font: { color: T.title, size: cell ? 11 : 12 } } } : {}),
    })}
  }

  if (tab === 'csd') {
    return { traces: [
      line(d.freqs, d.magnitude, 'Magnitude', 'solid', 'y', colors[0]),
      line(d.freqs, d.phase_deg, 'Phase [°]', 'solid', 'y2', colors[1]),
    ], layout: merge(L, titled({
      xaxis:  { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis:  { ...L.yaxis, title: withUnit('|CSD|', csdUnit(units.x, units.y)) },
      yaxis2: { ...L.yaxis, title: 'Phase [°]', overlaying: 'y', side: 'right' },
    }))}
  }

  if (tab === 'coherence') {
    return { traces: [line(d.freqs, d.Cxy, 'Coherence', 'solid', 'y', colors[0])], layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Coherence', range: [0, 1] },
    }))}
  }

  if (tab === 'filter') {
    const dr = ds(d.times, d.signal_raw)
    const df = ds(d.times, d.signal_filtered)
    return { traces: [
      line(dr.x, dr.y, 'Raw', 'dash', 'y', colors[0]),
      line(df.x, df.y, 'Filtered', 'solid', 'y', colors[1]),
    ], layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Time [s]', ...xAxisRange },
      yaxis: { ...L.yaxis, title: withUnit('Amplitude', oneUnit) },
    }))}
  }

  if (tab === 'stft' || tab === 'cwt') {
    return { traces: heatmap(d.times, d.freqs, d.magnitude, { carriesSignalUnit: true }),
             layout: merge(L, titled(tfAxes())) }
  }

  if (tab === 'wvd') {
    return { traces: heatmap(d.times, d.freqs, d.wvd),
             layout: merge(L, titled(tfAxes())) }
  }

  if (tab === 'spwvd') {
    return { traces: heatmap(d.times, d.freqs, d.spwvd),
             layout: merge(L, titled(tfAxes())) }
  }

  if (tab === 'instantaneous') {
    const s = ds(d.times, d.signal)
    const e = ds(d.times, d.envelope)
    const f = ds(d.times, d.inst_freq)
    return { traces: [
      line(s.x, s.y, 'Signal', 'dash', 'y', colors[0]),
      line(e.x, e.y, 'Envelope', 'solid', 'y', colors[1]),
      line(f.x, f.y, 'Inst. Freq [Hz]', 'solid', 'y2', colors[2]),
    ], layout: merge(L, titled({
      xaxis:  { ...L.xaxis, title: 'Time [s]', ...xAxisRange },
      yaxis:  { ...L.yaxis, title: withUnit('Amplitude', oneUnit) },
      yaxis2: { ...L.yaxis, title: 'Inst. Freq [Hz]', overlaying: 'y', side: 'right' },
    }))}
  }

  if (tab === 'emd') {
    const traces = d.imfs.map((imf, i) => ({
      x: d.times, y: imf, type: 'scatter', mode: 'lines', name: `IMF ${i + 1}`,
      line: { color: colors[i % colors.length] },
    }))
    traces.push({ x: d.times, y: d.residue, type: 'scatter', mode: 'lines',
                  name: 'Residue', line: { dash: 'dot' } })
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Time [s]' },
      yaxis: { ...L.yaxis, title: withUnit('Amplitude', oneUnit) },
    }))}
  }

  if (tab === 'hht') {
    const traces = d.inst_freqs.map((fi, i) => ({
      x: d.times, y: fi, mode: 'markers',
      marker: { color: d.envelopes[i], colorscale: 'Viridis', size: 3,
                showscale: i === 0, colorbar: { thickness: 12, outlinewidth: 0 } },
      name: `IMF ${i + 1}`, type: 'scatter',
    }))
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Time [s]' },
      yaxis: { ...L.yaxis, title: 'Inst. Freq [Hz]' },
      title: { text: title ?? 'HHT time-frequency representation',
               font: { color: T.title, size: cell ? 11 : 13 } },
    })}
  }

  if (tab === 'peaks') {
    const traces = [
      line(d.freqs, d.spectrum, 'Spectrum', 'solid', 'y', colors[0]),
      { x: d.peak_freqs, y: d.peak_values, type: 'scatter', mode: 'markers', name: 'Peaks',
        marker: { symbol: 'triangle-up', size: cell ? 7 : 10, color: T.danger } },
    ]
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: withUnit('Amplitude', oneUnit), type: yType },
    }))}
  }

  if (tab === 'indicators') {
    const traces = [
      { x: d.rms_times, y: d.rms_values, type: 'scatter', mode: 'lines',
        name: 'RMS', line: { color: colors[0] }, yaxis: 'y' },
      { x: d.energy_times, y: d.energy_values, type: 'scatter', mode: 'lines',
        name: 'Energy', line: { color: colors[1] }, yaxis: 'y2' },
      { x: d.freq_times, y: d.dominant_freqs, type: 'scatter', mode: 'lines',
        name: 'Dom. freq', line: { color: colors[2] }, yaxis: 'y3' },
    ]
    const stats = `Entropy: ${d.spectral_entropy.toFixed(3)}  |  Kurtosis: ${d.kurtosis.toFixed(3)}  |  Skewness: ${d.skewness.toFixed(3)}`
    return { traces, layout: merge(L, {
      xaxis:  { ...L.xaxis, title: 'Time [s]' },
      yaxis:  { ...L.yaxis, title: 'RMS', domain: [0.72, 1.0] },
      yaxis2: { ...L.yaxis, title: 'Energy', domain: [0.36, 0.66], anchor: 'x' },
      yaxis3: { ...L.yaxis, title: 'Freq [Hz]', domain: [0.0, 0.30], anchor: 'x' },
      title: { text: title ? `${title} — ${stats}` : stats,
               font: { color: T.title, size: cell ? 10 : 12 } },
    })}
  }

  if (tab === 'multisensor') {
    if (d.R) {
      return { traces: [{
        z: d.R, x: d.labels, y: d.labels, type: 'heatmap', colorscale: 'RdBu',
        zmin: -1, zmax: 1, colorbar: { thickness: 14, outlinewidth: 0 },
        text: d.R.map(row => row.map(v => v.toFixed(3))),
        texttemplate: '%{text}', textfont: { size: 11 },
      }], layout: merge(L, {
        title: { text: title ?? 'Correlation Matrix', font: { color: T.title } },
        yaxis: { ...L.yaxis, autorange: 'reversed' },
      })}
    }
    if (d.pairs) {
      const traces = d.pairs.map((p, i) =>
        line(d.freqs, p.Cxy, p.label, 'solid', 'y', colors[i % colors.length]))
      return { traces, layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...L.yaxis, title: 'Coherence', range: [0, 1] },
        title: { text: title ?? 'Coherence Matrix', font: { color: T.title } },
      })}
    }
    return null
  }

  if (tab === 'mutual_info') {
    const sig = d.significance
    const scanned = d.lags_s.length > 1
    const traces = []

    if (scanned) {
      traces.push(line(d.lags_s, d.mi, 'Mutual information', 'solid', 'y', colors[0]))
      // The null floor is the whole reason the curve is readable: MI is biased
      // upward by the estimator itself, so the interesting quantity is how far
      // above this line the peak sits, not its height.
      traces.push({
        x: [d.lags_s[0], d.lags_s[d.lags_s.length - 1]],
        y: [sig.null_p95, sig.null_p95],
        type: 'scatter', mode: 'lines', name: 'null 95th pct',
        line: { color: T.warning, dash: 'dash', width: 1.5 },
      })
      traces.push({
        x: [sig.lag_s], y: [sig.mi], type: 'scatter', mode: 'markers',
        name: `peak, lag ${sig.lag_s.toPrecision(3)} s`,
        marker: { symbol: 'circle-open', size: 13, line: { width: 2 }, color: T.danger },
      })
    } else {
      // A single lag is a bar against its null rather than a curve.
      traces.push({
        x: ['mutual information', 'null mean', 'null 95th pct'],
        y: [sig.mi, sig.null_mean, sig.null_p95],
        type: 'bar',
        marker: { color: [colors[0], T.text, T.warning] },
        name: 'nats',
      })
    }

    const verdict = sig.p_value <= 0.05
      ? `p = ${sig.p_value.toFixed(3)} — above the null`
      : `p = ${sig.p_value.toFixed(3)} — not distinguishable from the null`
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: scanned ? 'Lag [s]' : '' },
      yaxis: { ...L.yaxis, title: 'Mutual information [nats]', rangemode: 'tozero' },
      title: { text: title ?? `${d.x_label} vs ${d.y_label} — ${verdict}`,
               font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'frf') {
    // Magnitude on log-y: an FRF spans decades between resonance and
    // anti-resonance, and a linear axis shows only the peaks.
    const traces = d.inputs.map((it, i) =>
      line(d.freqs, it.magnitude, it.name, 'solid', 'y', colors[i % colors.length]))
    const head = d.mode === 'mimo'
      ? `FRF to ${d.output} from ${d.inputs.length} inputs (multi-input H1)`
      : `FRF ${d.inputs[0].name} to ${d.output} (${d.estimator})`
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Magnitude', type: 'log' },
      title: { text: title ?? head, font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'response_spectrum') {
    // One line per damping ratio. Log-log is the convention, and it is the
    // right one: both axes span decades.
    const traces = d.curves.map((c, i) =>
      line(d.periods, c[rsQuantity] ?? c.PSa, `${(c.zeta * 100).toFixed(0)}%`,
           'solid', 'y', colors[i % colors.length]))
    const LABEL = {
      Sd: 'Displacement', Sv: 'Velocity (true)', Sa: 'Acceleration (true)',
      PSv: 'Pseudo-velocity', PSa: 'Pseudo-acceleration',
    }
    const warn = d.n_below_limit
      ? `  ·  ${d.n_below_limit} point(s) below ${d.resolution_limit_s.toPrecision(3)} s are unreliable at this sample rate`
      : ''
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Period [s]', type: 'log' },
      yaxis: { ...L.yaxis, title: LABEL[rsQuantity] ?? rsQuantity, type: 'log' },
      title: { text: (title ?? `Response spectrum — ${d.name}`) + warn,
               font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'random_decrement') {
    const ok = d.levels.filter(l => l.signature)
    // Normalising is what makes the comparison meaningful: for a linear system
    // the *shape* is independent of trigger level, and only the amplitude
    // scales with it. Un-normalised, every curve simply sits at its own level
    // and tells you nothing you did not already know.
    const traces = ok.map((l, i) => {
      const y = rdtNormalize && l.peak > 0
        ? l.signature.map(v => v / l.peak)
        : l.signature
      const fit = l.zeta_pct !== undefined ? ` — ${l.zeta_pct.toFixed(2)}%` : ''
      return line(d.tau, y, `${l.level_sd.toFixed(1)} sd${fit}`, 'solid', 'y',
                  colors[i % colors.length])
    })
    const zs = ok.filter(l => l.zeta_pct !== undefined).map(l => l.zeta_pct)
    let verdict = ''
    if (zs.length > 1) {
      const lo = Math.min(...zs), hi = Math.max(...zs)
      const spread = 100 * (hi - lo) / ((hi + lo) / 2)
      verdict = spread > 20
        ? `  ·  damping varies ${lo.toFixed(2)}-${hi.toFixed(2)}% with level — amplitude-dependent`
        : `  ·  damping ${lo.toFixed(2)}-${hi.toFixed(2)}% across levels — consistent`
    }
    const bnd = d.band ? `  ·  ${d.band[0]}-${d.band[1]} Hz` : ''
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Lag [s]' },
      yaxis: { ...L.yaxis,
               title: rdtNormalize ? 'Signature (normalised)'
                                   : withUnit('Signature', oneUnit) },
      title: { text: (title ?? `Random decrement — ${d.name}${d.cross_name ? ` to ${d.cross_name}` : ''}`) + bnd + verdict,
               font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'log_decrement') {
    // The decay with the peaks the fit actually used marked on it: the whole
    // question is whether those are the peaks of the decay or of the noise.
    const SRC = { decay: 'free decay', autocorrelation: 'autocorrelation',
                  random_decrement: 'random decrement' }
    const traces = [
      line(d.times, d.signal, SRC[d.source] ?? d.name, 'solid', 'y', colors[0]),
      { x: d.peak_times, y: d.peak_amplitudes, type: 'scatter', mode: 'markers',
        name: `${d.n_peaks_used} peaks fitted`,
        marker: { symbol: 'circle-open', size: 8, line: { width: 2 }, color: T.danger } },
    ]
    const via = d.source && d.source !== 'decay' ? `  ·  via ${SRC[d.source]}` : ''
    const bnd = d.band ? `  ·  ${d.band[0]}-${d.band[1]} Hz` : ''
    const head = `zeta ${d.zeta_pct.toFixed(2)}%  ·  fn ${d.fn.toPrecision(4)} Hz  ·  R2 ${d.r_squared.toFixed(4)}${via}${bnd}`
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: d.source === 'decay' ? 'Time [s]' : 'Lag [s]' },
      yaxis: { ...L.yaxis, title: withUnit('Amplitude', oneUnit) },
      title: { text: title ?? head, font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'envelope') {
    const traces = [line(d.freqs, d.spectrum, 'Envelope spectrum', 'solid', 'y', colors[0])]
    const band = d.band ? `  ·  band ${d.band[0].toFixed(0)}-${d.band[1].toFixed(0)} Hz` : '  ·  no band (whole signal)'
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Modulation frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Envelope spectrum', type: yLog ? 'log' : 'linear' },
      title: { text: (title ?? `${d.name} — envelope spectrum`) + band,
               font: { color: T.title, size: cell ? 11 : 12 } },
    })}
  }

  if (tab === 'predictability') {
    const items = d.mode === 'partial'
      ? d.pairs.map(pp => ({ name: pp.label, values: pp.values }))
      : d.signals.map(sg => ({ name: sg.name, values: sg.values }))
    const head = d.mode === 'partial'
      ? 'Partial coherence — each pair with the other channels conditioned out'
      : 'Multiple coherence — how much of each channel the others explain'
    return { traces: items.map((it, i) =>
      line(d.freqs, it.values, it.name, 'solid', 'y', colors[i % colors.length])),
      layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
        // Both quantities are shares of variance, so the axis is the full 0-1
        // range whatever the data does. Letting it autoscale would make a flat
        // curve near zero look like structure.
        yaxis: { ...L.yaxis, title: 'Coherence', range: [0, 1] },
        title: { text: title ?? head, font: { color: T.title, size: cell ? 11 : 12 } },
      })}
  }

  if (tab === 'fdd') {
    const nSv = d.S[0]?.length ?? 0
    const traces = []
    for (let sv = 0; sv < nSv; sv++) {
      const vals = d.S.map(row => 10 * Math.log10(Math.max(row[sv], 1e-30)))
      traces.push(line(d.freqs, vals, `SV${sv + 1}`, 'solid', 'y', colors[sv % colors.length]))
    }
    if (d.peak_freqs?.length) {
      const sv1 = d.S.map(row => 10 * Math.log10(Math.max(row[0], 1e-30)))
      const peakVals = d.peak_freqs.map(f => {
        const idx = d.freqs.reduce((best, freq, i) =>
          Math.abs(freq - f) < Math.abs(d.freqs[best] - f) ? i : best, 0)
        return sv1[idx]
      })
      traces.push({ x: d.peak_freqs, y: peakVals, type: 'scatter', mode: 'markers',
                    name: 'Peaks',
                    marker: { symbol: 'triangle-up', size: cell ? 9 : 12, color: T.danger } })
    }
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Singular Value [dB]' },
      title: { text: title ?? 'FDD — Singular Values',
               font: { color: T.title, size: cell ? 11 : 13 } },
    })}
  }

  if (tab === 'statistics') {
    if (d.signals?.[0]?.qq) {
      const traces = []
      d.signals.forEach((sg, i) => {
        const c = colors[i % colors.length]
        traces.push({
          x: sg.qq.theoretical, y: sg.qq.ordered, type: 'scatter', mode: 'markers',
          name: sg.name, marker: { color: c, size: 4, opacity: 0.7 },
        })
        // The straight line is what normal data would fall on; the interest is
        // entirely in how the points leave it at the ends.
        const x0 = sg.qq.theoretical[0]
        const x1 = sg.qq.theoretical[sg.qq.theoretical.length - 1]
        traces.push({
          x: [x0, x1],
          y: [sg.qq.slope * x0 + sg.qq.intercept, sg.qq.slope * x1 + sg.qq.intercept],
          type: 'scatter', mode: 'lines', name: `${sg.name} reference`,
          line: { color: c, dash: 'dash', width: 1 }, showlegend: false,
        })
      })
      return { traces, layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Theoretical quantiles (normal)' },
        yaxis: { ...L.yaxis, title: withUnit('Sample quantiles', oneUnit) },
        title: { text: title ?? 'Q-Q against a normal distribution — points leaving the line at the ends are the departure',
                 font: { color: T.title, size: cell ? 11 : 12 } },
      })}
    }
    if (d.signals?.[0]?.xi) {
      // One channel or several. Each keeps a single hue across both its marks,
      // so the histogram and the curve read as one series rather than two.
      const multi = d.signals.length > 1
      const traces = []
      d.signals.forEach((sg, i) => {
        const c = colors[i % colors.length]
        if (showHist) {
          traces.push({
            x: sg.bin_centres, y: sg.hist_density, type: 'bar',
            name: multi ? `${sg.name} hist` : 'Histogram',
            marker: { color: c, opacity: multi ? 0.28 : 0.4 },
          })
        }
        if (showKde) {
          traces.push(line(sg.xi, sg.density, multi ? sg.name : 'KDE', 'solid', 'y', c))
        }
      })
      return { traces, layout: merge(L, {
        xaxis: { ...L.xaxis, title: withUnit('Value', oneUnit) },
        yaxis: { ...L.yaxis, title: withUnit('Density', densityUnit(oneUnit)) },
        barmode: 'overlay',
        title: { text: title ?? 'Probability Density', font: { color: T.title } },
      })}
    }
    if (d.H) {
      const traces = []
      if (showHist) {
        traces.push({
          x: d.x_centres, y: d.y_centres, z: d.H, type: 'heatmap', colorscale: 'Viridis',
          colorbar: { thickness: 14, outlinewidth: 0 },
        })
      }
      // Iso-probability contours from the 2-D KDE. Plotly's `contours` only
      // takes an evenly spaced start/end/size, so each level is its own trace —
      // the levels are chosen by enclosed mass and are not evenly spaced.
      if (showKde && d.kde?.levels?.length) {
        d.kde.levels.forEach((lv, i) => {
          traces.push({
            x: d.kde.x, y: d.kde.y, z: d.kde.z,
            type: 'contour',
            contours: { start: lv.level, end: lv.level, size: 0, coloring: 'none' },
            line: { color: colors[i % colors.length], width: 2 },
            name: `${Math.round(lv.mass * 100)}%`,
            showlegend: true, showscale: false, hoverinfo: 'name',
          })
        })
      }
      const note = d.kde_note ? `  ·  ${d.kde_note}`
        : d.kde?.n_fitted && d.kde.n_fitted < d.kde.n_total
        ? `  ·  KDE on ${d.kde.n_fitted.toLocaleString()} of ${d.kde.n_total.toLocaleString()} samples`
        : ''
      return { traces, layout: merge(L, {
        xaxis: { ...L.xaxis, title: withUnit(d.xlabel, units.x) },
        yaxis: { ...L.yaxis, title: withUnit(d.ylabel, units.y) },
        title: { text: (title ?? 'Joint distribution — contours enclose 50 / 90 / 99% of samples') + note,
                 font: { color: T.title, size: cell ? 11 : 12 } },
      })}
    }
    if (d.C) {
      return { traces: [{
        z: d.C, x: d.labels, y: d.labels, type: 'heatmap', colorscale: 'RdBu',
        colorbar: { thickness: 14, outlinewidth: 0 },
        text: d.C.map(row => row.map(v => v.toPrecision(3))),
        texttemplate: '%{text}', textfont: { size: 11 },
      }], layout: merge(L, {
        title: { text: title ?? 'Covariance Matrix', font: { color: T.title } },
        yaxis: { ...L.yaxis, autorange: 'reversed' },
      })}
    }
    if (d.distances) {
      const thresh = d.threshold
      const pointColors = d.distances.map(v => v > thresh ? T.danger : colors[0])
      return { traces: [
        { x: d.times, y: d.distances, type: 'scatter', mode: 'markers',
          name: 'Mahalanobis', marker: { color: pointColors, size: 3 } },
        { x: [d.times[0], d.times[d.times.length - 1]], y: [thresh, thresh],
          type: 'scatter', mode: 'lines', name: `${d.percentile}th pct`,
          line: { color: T.warning, dash: 'dash' } },
      ], layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Time [s]' },
        yaxis: { ...L.yaxis, title: 'Mahalanobis Distance' },
        title: { text: title ?? 'Mahalanobis Distance — Outlier Detection', font: { color: T.title } },
      })}
    }
    return null
  }

  return null
}

/**
 * One reference channel against several others, overlaid on a single axis.
 *
 * @param tab    'cross_correlation' | 'csd' | 'coherence'
 * @param items  [{name, data}] — one entry per compared channel
 * @param opts   as buildPlot, plus `ref` (the reference channel's name)
 */
export function buildPairOverlay(tab, items, opts) {
  const { T, colors = T.series, lagSide = 'both', cell = false, ref = null, units = {} } = opts
  const L = baseLayout(T, cell)
  const usable = items.filter(it => it.data)
  if (!usable.length) return null

  // Every curve here is `ref` against one other channel, all on one axis. That
  // axis can only carry a unit if the reference *and* every compared channel
  // agree — one channel in mm among accelerometers makes the whole axis
  // unlabellable, which is the honest outcome.
  const overlayUnit = commonUnitByName(
    units.byName, [ref, ...usable.map(it => it.name)].filter(Boolean))
  // Normalization is per-payload and uniform across an overlay, so the first
  // one speaks for all of them.
  const rawCorr = usable[0].data.normalized === false
  const corrUnit = rawCorr ? squared(overlayUnit) : ''

  const line = (x, y, name, color) => ({
    x, y, type: 'scatter', mode: 'lines', name, line: { color },
  })
  const colorAt = (i) => colors[i % colors.length]
  const heading = (what) => ref ? `${what} — ${ref} vs ${usable.length} channel${usable.length > 1 ? 's' : ''}` : what

  if (tab === 'cross_correlation') {
    const first = usable[0].data
    const loLag = first.lags[0]
    const hiLag = first.lags[first.lags.length - 1]
    const lagRange =
      lagSide === 'positive' ? [0, hiLag] :
      lagSide === 'negative' ? [loLag, 0] : null

    const traces = usable.map((it, i) => line(it.data.lags, it.data.ccf, it.name, colorAt(i)))

    // Mark each curve's peak within the visible half — with several overlaid,
    // reading the lag off the x-axis by eye is exactly what goes wrong.
    const px = [], py = [], ptext = []
    for (const it of usable) {
      let bl = null, bv = null
      for (let i = 0; i < it.data.lags.length; i++) {
        const lag = it.data.lags[i]
        if (lagRange && (lag < lagRange[0] || lag > lagRange[1])) continue
        if (bv === null || Math.abs(it.data.ccf[i]) > Math.abs(bv)) { bv = it.data.ccf[i]; bl = lag }
      }
      if (bl !== null) { px.push(bl); py.push(bv); ptext.push(`${it.name}: ${bl.toPrecision(4)} s`) }
    }
    if (px.length) {
      traces.push({
        x: px, y: py, type: 'scatter', mode: 'markers', name: 'peaks',
        text: ptext, hoverinfo: 'text',
        marker: { symbol: 'circle-open', size: cell ? 8 : 11, line: { width: 2 }, color: T.danger },
      })
    }

    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Lag [s]',
               ...(lagRange ? { range: lagRange, autorange: false } : { autorange: true }) },
      yaxis: { ...L.yaxis, title: withUnit('CCF', corrUnit) },
      title: { text: heading('Cross-correlation'), font: { color: T.title, size: cell ? 11 : 13 } },
    })}
  }

  if (tab === 'csd') {
    return { traces: usable.map((it, i) => line(it.data.freqs, it.data.magnitude, it.name, colorAt(i))),
      layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...L.yaxis, title: withUnit('|CSD|', csdUnit(overlayUnit, overlayUnit)) },
        title: { text: heading('Cross-spectral density'), font: { color: T.title, size: cell ? 11 : 13 } },
      })}
  }

  if (tab === 'coherence') {
    return { traces: usable.map((it, i) => line(it.data.freqs, it.data.Cxy, it.name, colorAt(i))),
      layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...L.yaxis, title: 'Coherence', range: [0, 1] },
        title: { text: heading('Coherence'), font: { color: T.title, size: cell ? 11 : 13 } },
      })}
  }

  return null
}

/** The optional second pane under FFT and Coherence. */
export function buildPhasePlot(tab, d, opts) {
  const { T, colors = T.series } = opts
  const L = merge(baseLayout(T), { margin: { l: 60, r: 20, t: 10, b: 50 } })
  if (!d) return null

  if (tab === 'fft') {
    const traces = d.signals.map((sig, i) => ({
      x: d.freqs, y: sig.phase, type: 'scatter', mode: 'lines',
      name: sig.name, line: { color: colors[i % colors.length] },
    }))
    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Phase [°]' },
    })}
  }

  if (tab === 'coherence') {
    return { traces: [{
      x: d.freqs, y: d.phase_deg, type: 'scatter', mode: 'lines',
      name: 'Phase', line: { color: colors[1] },
    }], layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: 'Phase [°]' },
    })}
  }

  return null
}

/**
 * The Time-Frequency Explorer: one surface, with everything that reads it.
 *
 * Time series on top sharing the time axis, the spectrogram in the middle, the
 * PSD rotated on the right sharing the frequency axis. The point of the layout
 * is that a ridge on the surface can be traced *up* to the moment it happened
 * and *across* to the frequency it happened at, without reading numbers off two
 * separate charts.
 *
 * Every panel keeps one scale. When a frequency is picked, its energy-over-time
 * gets a fourth panel of its own rather than a second y-axis on the time
 * series: those are different quantities, and overlaying them would make where
 * the curves cross look meaningful when it is an artefact of the scaling — the
 * same mistake §3.4 of the TODO describes for the filter response.
 *
 * @param d    {tf, ts, psd, transform, pick} — pick is {time, freq} or nulls
 * @param opts as buildPlot, plus `units`
 */
export function buildExplorer(d, opts) {
  const { T, colors = T.series, tf = {}, units = {}, cell = false } = opts
  if (!d?.tf) return null

  const { times, freqs, z } = d.tf
  if (!times?.length || !freqs?.length || !z?.length) return null

  const L = baseLayout(T, cell)
  const sigUnit = units.focus ?? ''
  const pick = d.pick ?? {}
  const hasSlice = pick.freqIndex != null && pick.freqIndex >= 0

  // Rows are laid out top-down; the surface keeps the largest share because it
  // is the thing being read, and the others are there to read it with.
  const XD = [0, 0.80]
  const rows = hasSlice
    ? { ts: [0.80, 1.0], surf: [0.30, 0.74], slice: [0, 0.24] }
    : { ts: [0.78, 1.0], surf: [0, 0.72] }

  const { db = true, rangeDb = 60, clipPct = 99, colorscale = 'Viridis' } = tf
  let zz = z, zmin, zmax, zUnit
  if (db) {
    ({ z: zz, zmin, zmax } = toDecibels(z, rangeDb))
    zUnit = 'dB re peak'
  } else {
    const hi = percentileOf(z, clipPct), lo = percentileOf(z, 0)
    if (hi != null && lo != null && hi > lo) { zmin = lo; zmax = hi }
    // Same rule as the standalone tabs: only STFT and CWT magnitudes carry the
    // signal's unit; WVD and SPWVD are energy densities and stay bare.
    zUnit = (d.transform === 'stft' || d.transform === 'cwt' || d.transform === 'fsst')
      ? withUnit('magnitude', sigUnit) : 'magnitude'
  }

  const traces = [{
    x: times, y: freqs, z: zz, type: 'heatmap', colorscale,
    ...(zmin != null ? { zmin, zmax, zauto: false } : {}),
    xaxis: 'x', yaxis: 'y',
    colorbar: {
      thickness: 12, outlinewidth: 0, len: (rows.surf[1] - rows.surf[0]),
      y: rows.surf[0], yanchor: 'bottom', x: 1.02,
      title: { text: zUnit, side: 'right', font: { size: 10 } },
    },
    hovertemplate: `%{x:.4g} s, %{y:.4g} Hz — %{z:.3g} ${db ? 'dB' : ''}<extra></extra>`,
  }]

  // Top: the signal itself, on the surface's own time axis.
  if (d.ts?.times?.length) {
    traces.push({
      x: d.ts.times, y: d.ts.values, type: 'scatter', mode: 'lines',
      name: d.ts.name ?? 'signal', xaxis: 'x', yaxis: 'y2',
      line: { color: colors[0], width: 1 }, showlegend: false,
    })
  }

  // Right: the average spectrum, rotated so frequency stays vertical.
  if (d.psd?.freqs?.length) {
    traces.push({
      x: d.psd.values, y: d.psd.freqs, type: 'scatter', mode: 'lines',
      name: 'PSD', xaxis: 'x2', yaxis: 'y', showlegend: false,
      line: { color: colors[1], width: 1 },
      hovertemplate: '%{y:.4g} Hz — %{x:.3g}<extra>PSD</extra>',
    })
  }

  // The spectrum at the picked instant, drawn against the average so the
  // comparison is the chart rather than something you hold in your head.
  if (pick.spectrum?.length) {
    traces.push({
      x: pick.spectrum, y: freqs, type: 'scatter', mode: 'lines',
      name: 'at cursor', xaxis: 'x2', yaxis: 'y', showlegend: false,
      line: { color: T.danger, width: 1.5 },
      hovertemplate: `%{y:.4g} Hz — %{x:.3g}<extra>t = ${pick.time?.toPrecision?.(4)} s</extra>`,
    })
  }

  if (hasSlice && pick.envelope?.length) {
    traces.push({
      x: times, y: pick.envelope, type: 'scatter', mode: 'lines',
      name: 'envelope', xaxis: 'x', yaxis: 'y3', showlegend: false,
      line: { color: T.danger, width: 1.5 },
    })
  }

  // Crosshairs: which time and which frequency the slices were taken at.
  const shapes = []
  if (pick.time != null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y', x0: pick.time, x1: pick.time,
      y0: freqs[0], y1: freqs[freqs.length - 1],
      line: { color: T.danger, width: 1, dash: 'dot' },
    })
  }
  if (pick.freq != null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y', x0: times[0], x1: times[times.length - 1],
      y0: pick.freq, y1: pick.freq,
      line: { color: T.danger, width: 1, dash: 'dot' },
    })
  }

  const layout = merge(L, {
    margin: { l: 58, r: 78, t: 24, b: 42 },
    showlegend: false,
    shapes,
    hovermode: 'closest',
    // The surface's axes. Only the bottom-most panel carries the time label, so
    // the shared axis reads as one axis rather than three.
    xaxis: {
      ...L.xaxis, domain: XD, anchor: hasSlice ? 'y3' : 'y',
      title: hasSlice ? '' : 'Time [s]',
      ...(hasSlice ? { matches: 'x3' } : {}),
    },
    yaxis: { ...L.yaxis, domain: rows.surf, anchor: 'x', title: 'Frequency [Hz]' },
    yaxis2: {
      ...L.yaxis, domain: rows.ts, anchor: 'x',
      title: { text: withUnit('Signal', sigUnit), font: { size: 10 } },
      showticklabels: true,
    },
    xaxis2: {
      ...L.xaxis, domain: [0.83, 1.0], anchor: 'y',
      title: { text: withUnit('PSD', psdUnit(sigUnit)), font: { size: 10 } },
      // WVD and SPWVD surfaces go negative, so a cursor slice off them is
      // signed and would be truncated by a log axis.
      type: (d.transform === 'wvd' || d.transform === 'spwvd') ? 'linear' : 'log',
      showticklabels: false,
    },
  })

  if (hasSlice) {
    // A fourth row, sharing the time axis, for the picked frequency's energy.
    layout.xaxis3 = { ...L.xaxis, domain: XD, anchor: 'y3', title: 'Time [s]' }
    layout.yaxis3 = {
      ...L.yaxis, domain: rows.slice, anchor: 'x3',
      title: { text: `@ ${pick.freq?.toPrecision?.(4)} Hz`, font: { size: 10 } },
    }
    // The envelope trace and the shared axis have to agree on which x they use.
    for (const t of traces) if (t.yaxis === 'y3') t.xaxis = 'x3'
    layout.xaxis.matches = undefined
    layout.xaxis3.matches = 'x'
  }

  return { traces, layout }
}
