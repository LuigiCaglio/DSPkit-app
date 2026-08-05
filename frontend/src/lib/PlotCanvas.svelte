<script>
  import { onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  // One Plotly div. Takes a finished spec from plotSpec.js so the same chart
  // definition can be mounted in the main area, a grid cell, or an Overview row.
  let { spec = null, height = null, onRelayout = null } = $props()

  let el = $state(null)
  let observer = null
  let bound = false

  // react() initialises the div on first call, so this doubles as setup — there
  // is deliberately no onMount plot creation to race it.
  $effect(() => {
    const _ = spec
    if (!el) return
    Plotly.react(el, spec?.traces ?? [], spec?.layout ?? {}, { responsive: true })
    // Plotly only exposes .on() once the div is initialised, which react() has
    // just done. Bind once; purge() tears the handler down with the plot.
    if (onRelayout && !bound && typeof el.on === 'function') {
      el.on('plotly_relayout', onRelayout)
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
