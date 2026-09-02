<script>
  import { untrack } from 'svelte'
  import { paramsFor, remember } from '../paramStore.svelte.js'

  let {
    columnNames = [], selected = [],
    loading, runAnalysis,
  } = $props()

  const kept = paramsFor('frf', { estimator: 'H1', nperseg: 1024, window: 'hann' })
  let estimator = $state(kept.estimator)
  let nperseg   = $state(kept.nperseg)
  let window_   = $state(kept.window)

  // Which channels excite and which responds is the question this tab asks, so
  // it picks them itself rather than inheriting the generic pair selector.
  let inputs = $state([])
  let output = $state(null)
  let helpOpen = $state(false)

  // Default to something sensible: last selected channel as the output and the
  // rest as inputs, which matches a force-then-response column layout.
  //
  // The reads are untracked. Without that this effect both depends on `output`
  // and assigns to it, which Svelte 5 treats as an update loop -- it was
  // throwing rather than settling, which is why the tab appeared to crash.
  $effect(() => {
    const sel = selected
    if (!sel.length) return
    untrack(() => {
      if (output === null || !sel.includes(output)) {
        const out = sel[sel.length - 1]
        output = out
        inputs = sel.filter(c => c !== out)
      } else {
        // Keep the input list inside the current selection.
        const valid = inputs.filter(c => sel.includes(c) && c !== output)
        if (valid.length !== inputs.length) inputs = valid
      }
    })
  })

  const name = (i) => columnNames[i] ?? `Ch ${i}`
  function toggleInput(i) {
    inputs = inputs.includes(i) ? inputs.filter(c => c !== i) : [...inputs, i].sort((a, b) => a - b)
  }

  let usable = $derived(inputs.length > 0 && output !== null && !inputs.includes(output))
  let multi  = $derived(inputs.length > 1)

  function run() {
    runAnalysis('/api/frf/estimate', {
      input_cols: JSON.stringify(inputs),
      output_col: output,
      estimator, nperseg, window: window_,
    })
  }
  $effect(() => remember(kept, { estimator, nperseg, window: window_ }))
</script>

<div class="field">
  <label for="frf-out">
    Output (response)
    <button type="button" class="help-dot" aria-expanded={helpOpen}
            aria-label="About the estimators" onclick={() => helpOpen = !helpOpen}>?</button>
  </label>
  <select id="frf-out" bind:value={output}>
    {#each selected as c}<option value={c}>{name(c)}</option>{/each}
  </select>
</div>

<div class="field">
  <label>Inputs (excitation)</label>
  <div class="frf-inputs">
    {#each selected as c}
      {#if c !== output}
        <button class="frf-chip" class:on={inputs.includes(c)} onclick={() => toggleInput(c)}>
          {name(c)}
        </button>
      {/if}
    {/each}
  </div>
</div>

{#if !multi}
  <div class="field">
    <label for="frf-est">Estimator</label>
    <select id="frf-est" bind:value={estimator}>
      <option value="H1">H1 — noise on the output</option>
      <option value="H2">H2 — noise on the input</option>
      <option value="H3">H3 — geometric mean</option>
    </select>
  </div>
{/if}

<div class="field">
  <label for="frf-nperseg">nperseg</label>
  <input id="frf-nperseg" type="number" bind:value={nperseg} min="64" step="64" style="width:90px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    An FRF is the response per unit of excitation, at each frequency. The three
    estimators differ only in where they assume the noise is: <b>H1</b> assumes
    it is on the output and is biased low at resonance; <b>H2</b> assumes it is
    on the input and is better at anti-resonances; <b>H3</b> splits the
    difference. Where coherence is near 1 they agree and the choice does not
    matter — which is why coherence is drawn underneath.
    {#if multi}
      With several inputs the multi-input solution is used instead. The
      individual curves only mean something if the inputs can be told apart:
      watch the condition number, because coherence stays high even when they
      cannot.
    {/if}
    <button class="help-close" onclick={() => helpOpen = false} aria-label="Close">×</button>
  </div>
{/if}

{#if !usable}
  <div class="status" style="max-width:280px">
    Pick one output and at least one input. They have to be different channels —
    nothing excites itself.
  </div>
{/if}

<button class="btn btn-primary" onclick={run} disabled={loading || !usable}>
  {loading ? 'Running…' : (multi ? `Run (${inputs.length} inputs)` : 'Run')}
</button>
