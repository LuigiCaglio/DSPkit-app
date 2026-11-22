<script>
  import { onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  // One Plotly div. Takes a finished spec from plotSpec.js so the same chart
  // definition can be mounted in the main area, a grid cell, or an Overview row.
  let { spec = null, height = null, onRelayout = null, onSelected = null,
        onClick = null } = $props()

  let el = $state(null)
  let observer = null
  let bound = false

  /**
   * Carry legend-hidden traces over a redraw of the same chart. Zooming
   * re-fetches the window and hands over fresh traces, which would otherwise
   * bring back every series the user had clicked off in the legend. Only
   * applied when the redraw has exactly the same trace names, so a different
   * chart or channel set starts with everything shown.
   */
  function keepLegendHidden(div, traces) {
    const old = div?.data
    if (!old?.length) return traces
    const hidden = new Set(old.filter(t => t.visible === 'legendonly').map(t => t.name))
    if (!hidden.size) return traces
    const names = traces.map(t => t.name)
    if (names.length !== old.length || names.some((n, i) => n !== old[i].name)) return traces
    return traces.map(t => (hidden.has(t.name) && t.visible === undefined
      ? { ...t, visible: 'legendonly' } : t))
  }

  // react() initialises the div on first call, so this doubles as setup — there
  // is deliberately no onMount plot creation to race it.
  $effect(() => {
    const _ = spec
    if (!el) return
    Plotly.react(el, keepLegendHidden(el, spec?.traces ?? []), spec?.layout ?? {},
                 { responsive: true })
    // Plotly only exposes .on() once the div is initialised, which react() has
    // just done. Bound once, but as dispatchers that read the *current* handler
    // when the event fires. Binding the handlers themselves froze whichever
    // were set on the first draw: the main chart is reused across tabs, so
    // after opening FFT (zoom only) the FDD tab never got its click, and
    // picking a frequency on the singular-value curves did nothing.
    if (!bound && typeof el.on === 'function') {
      el.on('plotly_relayout', (e) => onRelayout?.(e))
      el.on('plotly_click', (e) => onClick?.(e))
      el.on('plotly_selected', (e) => onSelected?.(e))
      el.on('plotly_deselect', () => onSelected?.(null))
      bound = true
    }
  })

  // The plot lives inside flex/grid parents whose size settles after layout, and
  // Plotly's `responsive` only follows the window. Watch the box itself.
  $effect(() => {
    if (!el) return
    observer = new ResizeObserver(() => { if (el) Plotly.Plots.resize(el) })
    observer.observe(el)
    return () => { observer?.disconnect(); observer = null }
  })

  onDestroy(() => { if (el) Plotly.purge(el) })
</script>

<div bind:this={el} class="plot-canvas" style={height ? `height:${height}` : ''}></div>
