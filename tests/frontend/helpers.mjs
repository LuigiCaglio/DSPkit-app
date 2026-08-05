// Shared fixtures for the plotSpec tests.
//
// plotSpec.js is deliberately free of Svelte runes, so node can import it
// directly and the chart definitions are testable without a browser.

export const T = {
  paper: '#ffffff', bg: '#ffffff', text: '#000000', title: '#000000',
  grid: '#cccccc', legend: '#ffffff', border: '#cccccc',
  danger: '#cc0000', warning: '#ee9900',
  series: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'],
}

/** A record of `seconds` at `fs` Hz, as the timeseries endpoint returns it. */
export function timeseries(seconds, fs, freq = 7) {
  const n = Math.round(seconds * fs)
  const times = Array.from({ length: n }, (_, i) => i / fs)
  return {
    times_raw: times,
    n_proc: n,
    fs_proc: fs,
    preprocessed: false,
    signals: [{ name: 'ch1', signal_raw: times.map(t => Math.sin(2 * Math.PI * freq * t)) }],
  }
}

/** Lags from -1 to +1 s at 100 Hz, with a gaussian bump at `centre`. */
export function lagAxis() {
  const lags = []
  for (let i = -100; i <= 100; i++) lags.push(Number((i / 100).toFixed(4)))
  return lags
}

export function bump(lags, centre, amp) {
  return lags.map(t => amp * Math.exp(-((t - centre) ** 2) / 0.002))
}

/** A flat-ish spectrum over 0..500 Hz. */
export function spectrum(key = 'Pxx') {
  const freqs = Array.from({ length: 501 }, (_, i) => i)
  return { freqs, signals: [{ name: 'ch1', [key]: freqs.map(f => 1 / (1 + f)) }] }
}
