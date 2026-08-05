// Pure chart builders: (tab, data, opts) -> { traces, layout } for Plotly.react().
//
// These live outside PlotPanel so one analysis has exactly one chart definition,
// renderable into the main canvas, a small-multiples grid cell, or an Overview
// panel. Nothing here touches the DOM or component state.

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

function baseLayout(T, cell = false) {
  return {
    paper_bgcolor: T.paper,
    plot_bgcolor:  T.bg,
    font:          { color: T.text, size: cell ? 10 : 12 },
    margin:        cell ? { l: 46, r: 12, t: 26, b: 36 } : { l: 60, r: 20, t: 30, b: 50 },
    xaxis:         { gridcolor: T.grid, zerolinecolor: T.grid },
    yaxis:         { gridcolor: T.grid, zerolinecolor: T.grid },
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
  } = opts

  const L = baseLayout(T, cell)
  const yType = yLog ? 'log' : 'linear'

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

  const heatmap = (x, y, z) => [{
    x, y, z, type: 'heatmap', colorscale: 'Viridis',
    colorbar: { thickness: cell ? 10 : 14, outlinewidth: 0 },
  }]

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
      yaxis: { ...L.yaxis, title: normalize ? 'Amplitude (norm.)' : 'Amplitude', type: yType },
      title: { text: heading, font: { color: T.text, size: 11 } },
    })}
  }

  if (tab === 'fft') {
    const traces = d.signals.map((sig, i) =>
      line(d.freqs, norm(sig.amplitude), sig.name, 'solid', 'y', colors[i % colors.length]))
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis: { ...L.yaxis, title: normalize ? 'Amplitude (norm.)' : 'Amplitude', type: yType },
    }))}
  }

  if (tab === 'psd') {
    const traces = d.signals.map((sig, i) =>
      line(d.freqs, norm(sig.Pxx), sig.name, 'solid', 'y', colors[i % colors.length]))
    const xr = (psd.xMin !== '' && psd.xMin != null && psd.xMax !== '' && psd.xMax != null)
      ? [parseFloat(psd.xMin), parseFloat(psd.xMax)] : undefined
    const yr = (psd.yMin !== '' && psd.yMin != null && psd.yMax !== '' && psd.yMax != null)
      ? [parseFloat(psd.yMin), parseFloat(psd.yMax)] : undefined
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Frequency [Hz]',
               ...(xr ? { range: xr, autorange: false } : { autorange: true }) },
      yaxis: { ...L.yaxis, title: 'PSD', type: (psd.yLog ?? true) ? 'log' : 'linear',
               ...(yr ? { range: yr, autorange: false } : { autorange: true }) },
    }))}
  }

  if (tab === 'autocorrelation') {
    const traces = d.signals.map((sig, i) =>
      line(d.lags, sig.acf, sig.name, 'solid', 'y', colors[i % colors.length]))
    return { traces, layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Lag [s]' },
      yaxis: { ...L.yaxis, title: 'ACF' },
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

    const head = title ?? (peakLag !== null
      ? `Peak |CCF| ${peakVal.toPrecision(3)} at lag ${peakLag.toPrecision(4)} s`
      : null)

    return { traces, layout: merge(L, {
      xaxis: { ...L.xaxis, title: 'Lag [s]',
               ...(lagRange ? { range: lagRange, autorange: false } : { autorange: true }) },
      yaxis: { ...L.yaxis, title: 'CCF' },
      ...(head ? { title: { text: head, font: { color: T.title, size: cell ? 11 : 12 } } } : {}),
    })}
  }

  if (tab === 'csd') {
    return { traces: [
      line(d.freqs, d.magnitude, 'Magnitude', 'solid', 'y', colors[0]),
      line(d.freqs, d.phase_deg, 'Phase [°]', 'solid', 'y2', colors[1]),
    ], layout: merge(L, titled({
      xaxis:  { ...L.xaxis, title: 'Frequency [Hz]' },
      yaxis:  { ...L.yaxis, title: '|CSD|' },
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
      yaxis: { ...L.yaxis, title: 'Amplitude' },
    }))}
  }

  if (tab === 'stft' || tab === 'cwt') {
    return { traces: heatmap(d.times, d.freqs, d.magnitude), layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Time [s]' },
      yaxis: { ...L.yaxis, title: 'Frequency [Hz]' },
    }))}
  }

  if (tab === 'wvd') {
    return { traces: heatmap(d.times, d.freqs, d.wvd), layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Time [s]' },
      yaxis: { ...L.yaxis, title: 'Frequency [Hz]' },
    }))}
  }

  if (tab === 'spwvd') {
    return { traces: heatmap(d.times, d.freqs, d.spwvd), layout: merge(L, titled({
      xaxis: { ...L.xaxis, title: 'Time [s]' },
      yaxis: { ...L.yaxis, title: 'Frequency [Hz]' },
    }))}
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
      yaxis:  { ...L.yaxis, title: 'Amplitude' },
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
      yaxis: { ...L.yaxis, title: 'Amplitude' },
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
      yaxis: { ...L.yaxis, title: 'Amplitude', type: yType },
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
    if (d.xi) {
      return { traces: [
        { x: d.bin_centres, y: d.hist_density, type: 'bar', name: 'Histogram',
          marker: { color: colors[0], opacity: 0.4 } },
        line(d.xi, d.density, 'KDE', 'solid', 'y', T.danger),
      ], layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Value' },
        yaxis: { ...L.yaxis, title: 'Density' },
        barmode: 'overlay',
        title: { text: title ?? 'Probability Density', font: { color: T.title } },
      })}
    }
    if (d.H) {
      return { traces: [{
        x: d.x_centres, y: d.y_centres, z: d.H, type: 'heatmap', colorscale: 'Viridis',
        colorbar: { thickness: 14, outlinewidth: 0 },
      }], layout: merge(L, {
        xaxis: { ...L.xaxis, title: d.xlabel },
        yaxis: { ...L.yaxis, title: d.ylabel },
        title: { text: title ?? 'Joint Distribution', font: { color: T.title } },
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
  const { T, colors = T.series, lagSide = 'both', cell = false, ref = null } = opts
  const L = baseLayout(T, cell)
  const usable = items.filter(it => it.data)
  if (!usable.length) return null

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
      yaxis: { ...L.yaxis, title: 'CCF' },
      title: { text: heading('Cross-correlation'), font: { color: T.title, size: cell ? 11 : 13 } },
    })}
  }

  if (tab === 'csd') {
    return { traces: usable.map((it, i) => line(it.data.freqs, it.data.magnitude, it.name, colorAt(i))),
      layout: merge(L, {
        xaxis: { ...L.xaxis, title: 'Frequency [Hz]' },
        yaxis: { ...L.yaxis, title: '|CSD|' },
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
