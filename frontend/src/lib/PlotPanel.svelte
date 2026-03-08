<script>
  import { onMount, onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  let { activeTab, plotData, loading, plotError } = $props()

  let container = $state(null)

  const DARK_LAYOUT = {
    paper_bgcolor: '#0f1117',
    plot_bgcolor:  '#13151f',
    font:          { color: '#e2e8f0', size: 12 },
    margin:        { l: 60, r: 20, t: 30, b: 50 },
    xaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    yaxis:         { gridcolor: '#2d3148', zerolinecolor: '#2d3148' },
    legend:        { bgcolor: '#1a1d27', bordercolor: '#2d3148', borderwidth: 1 },
  }

  function merge(...objs) {
    return Object.assign({}, ...objs)
  }

  function draw() {
    if (!container || !plotData) return

    const tab = activeTab

    // ── line chart helper ────────────────────────────────────────────────────
    function line(x, y, name, dash = 'solid', yaxis = 'y') {
      return { x, y, type: 'scatter', mode: 'lines', name,
               line: { dash }, yaxis }
    }

    // ── heatmap helper ───────────────────────────────────────────────────────
    function heatmap(x, y, z) {
      return [{ x, y, z, type: 'heatmap', colorscale: 'Viridis',
                colorbar: { thickness: 14, outlinewidth: 0 } }]
    }

    if (tab === 'timeseries') {
      const preproc = plotData.n_proc !== plotData.times_raw.length || plotData.fs_raw !== plotData.fs_proc
      const nameX = plotData.col_name_x ?? 'Signal X'
      const nameY = plotData.col_name_y ?? 'Signal Y'
      const traces = []

      if (preproc) {
        traces.push({ x: plotData.times_raw,  y: plotData.signal_raw_x,
          type: 'scatter', mode: 'lines', name: `${nameX} raw`, line: { color: '#4b5563', dash: 'dot' } })
        traces.push({ x: plotData.times_proc, y: plotData.signal_proc_x,
          type: 'scatter', mode: 'lines', name: `${nameX}`, line: { color: '#6366f1' } })
        if (plotData.signal_raw_y) {
          traces.push({ x: plotData.times_raw,  y: plotData.signal_raw_y,
            type: 'scatter', mode: 'lines', name: `${nameY} raw`, line: { color: '#6b7280', dash: 'dot' } })
          traces.push({ x: plotData.times_proc, y: plotData.signal_proc_y,
            type: 'scatter', mode: 'lines', name: `${nameY}`, line: { color: '#f59e0b' } })
        }
      } else {
        traces.push({ x: plotData.times_raw, y: plotData.signal_raw_x,
          type: 'scatter', mode: 'lines', name: nameX, line: { color: '#6366f1' } })
        if (plotData.signal_raw_y) {
          traces.push({ x: plotData.times_raw, y: plotData.signal_raw_y,
            type: 'scatter', mode: 'lines', name: nameY, line: { color: '#f59e0b' } })
        }
      }

      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
          title: { text: `${plotData.n_proc.toLocaleString()} samples  ·  fs = ${plotData.fs_proc.toFixed(2)} Hz`,
                   font: { color: '#6b7280', size: 11 } },
        }))

    } else if (tab === 'fft') {
      const nameX = plotData.col_name_x ?? 'Signal X'
      const traces = [line(plotData.freqs, plotData.amplitude_x, nameX)]
      if (plotData.amplitude_y)
        traces.push(line(plotData.freqs, plotData.amplitude_y, plotData.col_name_y ?? 'Signal Y'))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'psd') {
      const nameX = plotData.col_name_x ?? 'Signal X'
      const traces = [line(plotData.freqs, plotData.Pxx_x, nameX)]
      if (plotData.Pxx_y)
        traces.push(line(plotData.freqs, plotData.Pxx_y, plotData.col_name_y ?? 'Signal Y'))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'PSD', type: 'log' },
        }))

    } else if (tab === 'autocorrelation') {
      const nameX = plotData.col_name_x ?? 'Signal X'
      const traces = [line(plotData.lags, plotData.acf_x, nameX)]
      if (plotData.acf_y)
        traces.push(line(plotData.lags, plotData.acf_y, plotData.col_name_y ?? 'Signal Y'))
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Lag [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'ACF' },
        }))

    } else if (tab === 'cross_correlation') {
      Plotly.react(container, [line(plotData.lags, plotData.ccf, 'CCF')],
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Lag [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'CCF' },
        }))

    } else if (tab === 'csd') {
      Plotly.react(container,
        [line(plotData.freqs, plotData.magnitude, 'Magnitude'),
         line(plotData.freqs, plotData.phase_deg, 'Phase [°]', 'solid', 'y2')],
        merge(DARK_LAYOUT, {
          xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis:  { ...DARK_LAYOUT.yaxis, title: '|CSD|' },
          yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Phase [°]', overlaying: 'y', side: 'right' },
        }))

    } else if (tab === 'coherence') {
      Plotly.react(container, [line(plotData.freqs, plotData.Cxy, 'Coherence')],
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Frequency [Hz]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Coherence', range: [0, 1] },
        }))

    } else if (tab === 'filter') {
      Plotly.react(container,
        [line(plotData.times, plotData.signal_raw,      'Raw',      'dash'),
         line(plotData.times, plotData.signal_filtered, 'Filtered', 'solid')],
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'stft' || tab === 'cwt') {
      const key = tab === 'stft' ? 'magnitude' : 'magnitude'
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData[key]),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'wvd') {
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData.wvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'spwvd') {
      Plotly.react(container,
        heatmap(plotData.times, plotData.freqs, plotData.spwvd),
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Frequency [Hz]' },
        }))

    } else if (tab === 'instantaneous') {
      Plotly.react(container,
        [line(plotData.times, plotData.signal,   'Signal',   'dash'),
         line(plotData.times, plotData.envelope, 'Envelope', 'solid'),
         line(plotData.times, plotData.inst_freq, 'Inst. Freq [Hz]', 'solid', 'y2')],
        merge(DARK_LAYOUT, {
          xaxis:  { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis:  { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
          yaxis2: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]', overlaying: 'y', side: 'right' },
        }))

    } else if (tab === 'emd') {
      const traces = plotData.imfs.map((imf, i) => ({
        x: plotData.times, y: imf,
        type: 'scatter', mode: 'lines', name: `IMF ${i + 1}`,
      }))
      traces.push({ x: plotData.times, y: plotData.residue,
        type: 'scatter', mode: 'lines', name: 'Residue', line: { dash: 'dot' } })
      Plotly.react(container, traces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Amplitude' },
        }))

    } else if (tab === 'hht') {
      // HHT time-frequency scatter (energy coloured by envelope)
      const tfTraces = plotData.inst_freqs.map((fi, i) => ({
        x: plotData.times, y: fi,
        mode: 'markers',
        marker: { color: plotData.envelopes[i], colorscale: 'Viridis', size: 3,
                  showscale: i === 0, colorbar: { thickness: 12, outlinewidth: 0 } },
        name: `IMF ${i + 1}`, type: 'scatter',
      }))
      Plotly.react(container, tfTraces,
        merge(DARK_LAYOUT, {
          xaxis: { ...DARK_LAYOUT.xaxis, title: 'Time [s]' },
          yaxis: { ...DARK_LAYOUT.yaxis, title: 'Inst. Freq [Hz]' },
          title: { text: 'HHT time-frequency representation', font: { color: '#a5b4fc' } },
        }))
    }
  }

  // Re-draw whenever plotData or activeTab changes
  $effect(() => {
    // touch reactive deps
    const _ = plotData
    const __ = activeTab
    draw()
  })

  onMount(() => {
    if (!container) return
    Plotly.newPlot(container, [], DARK_LAYOUT, { responsive: true })
  })

  onDestroy(() => {
    if (container) Plotly.purge(container)
  })
</script>

<div style="width:100%;height:100%;position:relative">
  {#if loading}
    <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:10;display:flex;flex-direction:column;align-items:center;gap:10px">
      <div class="spinner"></div>
      <div style="font-size:12px;color:#6b7280">Computing…</div>
    </div>
  {/if}

  {#if !plotData && !loading && !plotError}
    <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#4b5563;font-size:13px">
      Select an analysis and press Run.
    </div>
  {/if}

  <div bind:this={container} style="width:100%;height:100%"></div>
</div>
