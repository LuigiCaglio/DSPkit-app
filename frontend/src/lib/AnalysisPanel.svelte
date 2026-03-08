<script>
  import FftControls         from './controls/FftControls.svelte'
  import PsdControls         from './controls/PsdControls.svelte'
  import AutocorrControls    from './controls/AutocorrControls.svelte'
  import CrossCorrControls   from './controls/CrossCorrControls.svelte'
  import CsdControls         from './controls/CsdControls.svelte'
  import CoherenceControls   from './controls/CoherenceControls.svelte'
  import FilterControls      from './controls/FilterControls.svelte'
  import StftControls        from './controls/StftControls.svelte'
  import CwtControls         from './controls/CwtControls.svelte'
  import WvdControls         from './controls/WvdControls.svelte'
  import SpwvdControls       from './controls/SpwvdControls.svelte'
  import InstantControls     from './controls/InstantControls.svelte'
  import EmdControls         from './controls/EmdControls.svelte'
  import HhtControls         from './controls/HhtControls.svelte'
  import TimeseriesControls from './controls/TimeseriesControls.svelte'

  let { activeTab, dualSignal, signalColX, signalColY, timeCol, fsManual, loading, plotError, runAnalysis } = $props()
</script>

<div class="controls-area">
  {#if activeTab === 'timeseries'}
    <TimeseriesControls {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'fft'}
    <FftControls {loading} {runAnalysis} />
  {:else if activeTab === 'psd'}
    <PsdControls {loading} {runAnalysis} />
  {:else if activeTab === 'autocorrelation'}
    <AutocorrControls {loading} {runAnalysis} />
  {:else if activeTab === 'cross_correlation'}
    <CrossCorrControls {signalColX} {signalColY} {timeCol} {fsManual} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'csd'}
    <CsdControls {signalColX} {signalColY} {timeCol} {fsManual} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'coherence'}
    <CoherenceControls {signalColX} {signalColY} {timeCol} {fsManual} {loading} {runAnalysis} {dualSignal} />
  {:else if activeTab === 'filter'}
    <FilterControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'stft'}
    <StftControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'cwt'}
    <CwtControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'wvd'}
    <WvdControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'spwvd'}
    <SpwvdControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'instantaneous'}
    <InstantControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'emd'}
    <EmdControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {:else if activeTab === 'hht'}
    <HhtControls {signalColX} {timeCol} {fsManual} {loading} {runAnalysis} />
  {/if}

  {#if plotError}
    <div class="error" style="width:100%">Error: {plotError}</div>
  {/if}
</div>
