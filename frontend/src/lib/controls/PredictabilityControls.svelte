<script>
  import { paramsFor, remember } from '../paramStore.svelte.js'
  import { untrack } from 'svelte'

  let {
    loading, runAnalysis, dualSignal, autoRun = false,
    nSelected = 0, columnNames = [], selected = [],
  } = $props()

  const kept = paramsFor('predictability', { mode: 'multiple', nperseg: 1024 })
  let mode    = $state(kept.mode)
  let nperseg = $state(kept.nperseg)
  let target  = $state(null)

  // Multiple and partial coherence both come from the inverse of the
  // cross-spectral matrix, which is only full rank with more Welch averages
  // than channels; the library refuses below that. The error spectrum has no
  // such floor -- one channel explaining another is a perfectly good question
  // -- so it only needs a target and something to predict it with.
  let enough = $derived(mode === 'error' ? nSelected >= 2 : nSelected >= 3)

  // Keep the target inside the current selection. The reads are untracked
  // because this effect both depends on `target` and assigns to it, which
  // Svelte 5 treats as an update loop -- the same trap the FRF tab hit.
  $effect(() => {
    const sel = selected
    if (!sel.length) return
    untrack(() => {
      if (target === null || !sel.includes(target)) target = sel[0]
    })
  })

  const name = (i) => columnNames[i] ?? `Ch ${i}`
  let predictors = $derived(selected.filter(c => c !== target).map(name))

  // The error spectrum needs a target, and the effect above is what supplies
  // it. Auto-running from onMount raced that: on a restored session the tab
  // came back already in error mode and posted a target of null, which the API
  // correctly refused. Gate on the target being resolved instead of on mount.
  let ready = $derived(enough && (mode !== 'error' || target !== null))

  function run() {
    const params = { mode, nperseg }
    if (mode === 'error') {
      if (target === null) return
      params.target_col = target
    }
    runAnalysis('/api/multisensor/coherence_conditioned', params)
  }

  let autoRan = false
  $effect(() => {
    if (!autoRun || !ready || autoRan) return
    autoRan = true
    // Untracked: run() reads every parameter, and tracking them here would
    // re-fire this effect on each edit, turning one auto-run into a stream.
    untrack(() => run())
  })
  $effect(() => remember(kept, { mode, nperseg }))

  // Click, not hover. A native title tooltip waits about a second, targets a
  // 13px circle, and renders four sentences badly or truncates them — none of
  // which suits an explanation someone actually needs to read.
  let helpOpen = $state(null)          // 'measure' | 'nperseg' | null
  const toggleHelp = (k) => { helpOpen = helpOpen === k ? null : k }

  const NPERSEG_HELP =
    'Welch window length, in samples. It sets the frequency resolution ' +
    '(fs / nperseg) and how many segments get averaged, and those pull against ' +
    'each other: a longer window resolves a sharp resonance but leaves fewer ' +
    'segments, which lifts the whole curve.'

  const HELP = {
    multiple:
      'Multiple coherence. For each channel, the share of it that all the other ' +
      'selected channels together explain, at each frequency. 1 means fully ' +
      'predictable from the rest; 0 means it carries information nothing else does. ' +
      'Use it to find a redundant sensor, or one doing its own thing.',
    partial:
      'Partial coherence. The relationship between two channels once every other ' +
      'selected channel has been conditioned out. It separates a direct link from ' +
      'one running through a third sensor: two channels can both follow a common ' +
      'source and look strongly related, while nothing passes between them.',
    error:
      'Error spectrum. The same failure the coherence shows, but in the target ' +
      "channel's own units: what is left of it after the others have explained " +
      'what they can. Coherence is dimensionless and says where a model fails; ' +
      'only this says whether that matters. A band where coherence collapses is ' +
      'harmless if there is no power there, which is the usual case — coherence ' +
      'is worst exactly where there is nothing to be coherent about. ' +
      'It is sensitive to nperseg in both directions. Too short and leakage ' +
      'smears sharp peaks and notches, inventing a residual that is not there; ' +
      'the fake error grows as the square of the resolution bandwidth and is ' +
      'worst where the target is strongest. Too long and the averages run out, ' +
      'which biases coherence up and this curve down. Aim for a resolution ' +
      'about four times finer than the half-power width of the narrowest peak. ' +
      'The bundled 2-DOF file shows the trap: predicting x1_disp from the two ' +
      'force channels, the default 1024 calls 39% of the displacement ' +
      'unexplainable when the true answer is zero, and 8192 brings it to 1%.',
  }
</script>

<div class="field">
  <label for="pred-mode">
    Measure
    <button type="button" class="help-dot" aria-expanded={helpOpen === 'measure'}
            aria-label="What does this measure?"
            onclick={() => toggleHelp('measure')}>?</button>
  </label>
  <select id="pred-mode" bind:value={mode}>
    <option value="multiple">Multiple coherence</option>
    <option value="partial">Partial coherence</option>
    <option value="error">Error spectrum</option>
  </select>
</div>

{#if mode === 'error'}
  <div class="field">
    <label for="pred-target">Target (the channel to explain)</label>
    <select id="pred-target" bind:value={target}>
      {#each selected as c}<option value={c}>{name(c)}</option>{/each}
    </select>
  </div>
  {#if predictors.length}
    <div class="field">
      <label>Predictors</label>
      <div class="pred-list">{predictors.join(', ')}</div>
    </div>
  {/if}
{/if}

<div class="field">
  <label for="pred-nperseg">
    nperseg
    <button type="button" class="help-dot" aria-expanded={helpOpen === 'nperseg'}
            aria-label="What is nperseg?"
            onclick={() => toggleHelp('nperseg')}>?</button>
  </label>
  <input id="pred-nperseg" type="number" bind:value={nperseg} min="64" step="64" style="width:90px" />
</div>

{#if helpOpen}
  <div class="help-panel">
    {helpOpen === 'measure' ? HELP[mode] : NPERSEG_HELP}
    <button class="help-close" onclick={() => helpOpen = null} aria-label="Close">×</button>
  </div>
{/if}

<div class="status" style="max-width:340px">
  {#if !enough}
    {#if mode === 'error'}
      Needs at least 2 channels — one to explain, and one to explain it with.
    {:else}
      Needs at least 3 channels — with two there is nothing to condition out, so
      ordinary coherence on the Cross-Signal tab is the right tool.
    {/if}
  {:else if mode === 'error'}
    <strong>Set nperseg from the sharpest resonance, not from habit.</strong>
    Too short and leakage invents a residual that is not there, worst exactly
    where the target carries the most power. Too long and the averages run out,
    which biases this curve down instead. Check the bias floor reported under
    the plot, and see the <em>?</em> above for how far wrong it can go.
  {:else}
    A lightly damped resonance can be narrower than one frequency bin, and
    coherence reads <em>low</em> there for that reason alone. If a peak you expect
    to be explained is not, raise nperseg and see whether it climbs. Raising it
    also leaves fewer segments to average, which lifts the whole curve — the
    library warns when that starts to matter.
  {/if}
</div>

<button class="btn btn-primary" onclick={run} disabled={loading || !ready}>
  {loading ? 'Running…' : 'Run'}
</button>

<style>
  .pred-list {
    font-size: 12px;
    opacity: 0.8;
    max-width: 220px;
    line-height: 1.4;
  }
</style>
