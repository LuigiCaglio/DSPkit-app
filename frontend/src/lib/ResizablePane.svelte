<script>
  import { onMount } from 'svelte'

  // A vertically resizable box with a drag handle beneath it. Heights persist
  // per `id`, so the layout you set for your own data survives a reload.
  //
  // With `fill`, the pane starts as flex:1 (filling whatever space is going)
  // and only switches to an explicit pixel height once you drag it. Double-
  // clicking the handle puts it back.
  // `height` is bindable so several panes can share one value — the grid binds
  // every cell to the same number, which keeps its rows aligned while letting
  // you grab whichever cell you happen to be looking at. null means "fill".
  let {
    id = null,
    initial = 300,
    min = 140,
    max = 2000,
    fill = false,
    label = 'Resize panel',
    height = $bindable(undefined),
    children,
  } = $props()

  // Unbound usage still needs a starting value.
  if (height === undefined) height = fill ? null : initial

  let box      = $state(null)
  let dragging = $state(false)

  const key = id ? `dspkit.paneHeight.${id}` : null

  onMount(() => {
    if (!key) return
    try {
      const v = localStorage.getItem(key)
      if (v != null) height = v === 'fill' ? null : Number(v)
    } catch { /* private mode / storage disabled — defaults are fine */ }
  })

  function persist() {
    if (!key) return
    try { localStorage.setItem(key, height == null ? 'fill' : String(height)) } catch { /* ignore */ }
  }

  const clamp = (v) => Math.min(max, Math.max(min, v))
  /** Rendered height — the starting point while `height` is still null (fill). */
  const measured = () => box?.getBoundingClientRect().height ?? height ?? initial

  let startY = 0
  let startH = 0

  function onPointerDown(e) {
    startY = e.clientY
    startH = measured()
    dragging = true
    e.currentTarget.setPointerCapture(e.pointerId)
    e.preventDefault()
  }
  function onPointerMove(e) {
    if (!dragging) return
    height = clamp(startH + (e.clientY - startY))
  }
  function onPointerUp(e) {
    if (!dragging) return
    dragging = false
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* already gone */ }
    persist()
  }
  function reset() {
    height = fill ? null : initial
    persist()
  }
  function nudge(dy) {
    height = clamp(measured() + dy)
    persist()
  }
  function onKeyDown(e) {
    if (e.key === 'ArrowUp')        { nudge(-24); e.preventDefault() }
    else if (e.key === 'ArrowDown') { nudge(24);  e.preventDefault() }
    else if (e.key === 'Home')      { reset();    e.preventDefault() }
  }
</script>

<!-- Single root: as a CSS-grid child, two roots would put the pane and its
     handle in separate grid cells. -->
<div class="pane-outer" class:filling={height == null}>
<div
  class="pane"
  class:filling={height == null}
  bind:this={box}
  style={height == null ? '' : `height:${height}px;flex:0 0 ${height}px`}
>
  {@render children()}
</div>

<div
  class="pane-handle"
  class:dragging
  role="separator"
  aria-orientation="horizontal"
  aria-label={label}
  tabindex="0"
  title="Drag to resize · double-click to reset"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
  ondblclick={reset}
  onkeydown={onKeyDown}
>
  <span class="pane-grip"></span>
</div>
</div>

<style>
  .pane-outer {
    display: flex;
    flex-direction: column;
    min-height: 0;
    /* Must not shrink: the inner pane has a fixed height once dragged, so a
       shrinking wrapper would clip it rather than let .plot-wrap scroll. */
    flex: 0 0 auto;
  }
  /* Fill mode has to propagate through the wrapper, or the inner pane would
     only ever fill a wrapper that had already collapsed to its content. */
  .pane-outer.filling { flex: 1; }

  .pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
    position: relative;
  }
  .pane.filling { flex: 1; }

  .pane-handle {
    flex: 0 0 auto;
    height: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: ns-resize;
    /* Widen the grab target beyond the visual strip without moving anything. */
    margin: -2px 0;
    padding: 2px 0;
    background: transparent;
    transition: background var(--transition);
    touch-action: none;
  }
  .pane-handle:hover,
  .pane-handle:focus-visible,
  .pane-handle.dragging { background: var(--bg-hover); }
  .pane-handle:focus-visible { outline: 1px solid var(--accent); outline-offset: -1px; }

  .pane-grip {
    width: 46px;
    height: 3px;
    border-radius: 2px;
    background: var(--border-light);
    transition: background var(--transition);
  }
  .pane-handle:hover .pane-grip,
  .pane-handle:focus-visible .pane-grip,
  .pane-handle.dragging .pane-grip { background: var(--accent); }
</style>
