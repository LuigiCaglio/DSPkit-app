/**
 * Theme system — single source of truth for app chrome AND plot colours.
 *
 * Chrome tokens are written to <html> as CSS custom properties; app.css is
 * authored entirely against them. Plot colours are resolved from the same
 * definitions in JS (not via getComputedStyle) so Plotly redraws can't race
 * the stylesheet.
 *
 * Series colours are per *mode*, not per theme: a channel keeps its colour
 * when you switch theme. Both sets are validated categorical palettes
 * (lightness band, chroma floor, CVD separation, normal-vision floor,
 * contrast vs. surface) — see scripts/validate_palette.js in the dataviz
 * skill. Do not hand-edit a slot without re-running it.
 */

// Fixed hue order — assigned by index, never cycled through a generator.
export const SERIES_DARK = [
  '#3987e5', '#d95926', '#199e70', '#c98500',
  '#d55181', '#008300', '#9085e9', '#e66767',
]
export const SERIES_LIGHT = [
  '#2a78d6', '#eb6834', '#1baf7a', '#eda100',
  '#e87ba4', '#008300', '#4a3aa7', '#e34948',
]

/** Chrome + plot tokens per theme. Keys become `--kebab-case` CSS vars. */
export const THEMES = [
  {
    id: 'midnight', name: 'Midnight', mode: 'dark',
    tokens: {
      bgBase: '#0f1117', bgSurface: '#1a1d27', bgPanel: '#13151f',
      bgRaised: '#1e2235', bgHover: '#23263a',
      border: '#2d3148', borderLight: '#374151',
      accent: '#6366f1', accentHover: '#4f46e5',
      accentContrast: '#ffffff', accentText: '#a5b4fc',
      textPrimary: '#e2e8f0', textSecondary: '#94a3b8',
      textMuted: '#6b7280', textFaint: '#4b5563',
      danger: '#f87171', success: '#34d399', warning: '#fbbf24',
      plotPaper: '#0f1117', plotBg: '#13151f', plotGrid: '#2d3148',
    },
  },
  {
    id: 'ocean', name: 'Ocean', mode: 'dark',
    tokens: {
      bgBase: '#0a192f', bgSurface: '#112240', bgPanel: '#0d1f3c',
      bgRaised: '#1d3557', bgHover: '#264573',
      border: '#1e3a5f', borderLight: '#2d5986',
      accent: '#64ffda', accentHover: '#9effea',
      accentContrast: '#06231d', accentText: '#64ffda',
      textPrimary: '#ccd6f6', textSecondary: '#8892b0',
      textMuted: '#5f6b85', textFaint: '#44506b',
      danger: '#ff6b6b', success: '#4ade80', warning: '#ffd166',
      plotPaper: '#0a192f', plotBg: '#0a192f', plotGrid: '#1e3a5f',
    },
  },
  {
    id: 'charcoal', name: 'Charcoal', mode: 'dark',
    tokens: {
      bgBase: '#1e1e1e', bgSurface: '#252526', bgPanel: '#1b1b1b',
      bgRaised: '#2d2d30', bgHover: '#3c3c3c',
      border: '#3a3a3a', borderLight: '#4a4a4a',
      accent: '#569cd6', accentHover: '#9cdcfe',
      accentContrast: '#0b1a26', accentText: '#9cdcfe',
      textPrimary: '#d4d4d4', textSecondary: '#9da5b4',
      textMuted: '#808080', textFaint: '#5a5a5a',
      danger: '#f14c4c', success: '#4ec9b0', warning: '#dcdcaa',
      plotPaper: '#1e1e1e', plotBg: '#1e1e1e', plotGrid: '#3a3a3a',
    },
  },
  {
    id: 'light', name: 'Light', mode: 'light',
    tokens: {
      bgBase: '#f4f6fa', bgSurface: '#ffffff', bgPanel: '#eef1f7',
      bgRaised: '#ffffff', bgHover: '#e6ebf4',
      border: '#d4dbe8', borderLight: '#c3ccdb',
      accent: '#2563eb', accentHover: '#1d4ed8',
      accentContrast: '#ffffff', accentText: '#1d4ed8',
      textPrimary: '#1a1d2e', textSecondary: '#4a5568',
      textMuted: '#6b7280', textFaint: '#9aa4b2',
      danger: '#dc2626', success: '#059669', warning: '#b45309',
      plotPaper: '#ffffff', plotBg: '#ffffff', plotGrid: '#e2e6ee',
    },
  },
  {
    id: 'daylight', name: 'Daylight', mode: 'light',
    tokens: {
      bgBase: '#f6faf8', bgSurface: '#ffffff', bgPanel: '#eef7f3',
      bgRaised: '#ffffff', bgHover: '#e2f3ec',
      border: '#d2e7de', borderLight: '#bfdcd0',
      accent: '#10b981', accentHover: '#059669',
      accentContrast: '#ffffff', accentText: '#047857',
      textPrimary: '#122621', textSecondary: '#425f56',
      textMuted: '#6b8880', textFaint: '#9fb7b0',
      danger: '#dc2626', success: '#0284c7', warning: '#b45309',
      plotPaper: '#ffffff', plotBg: '#ffffff', plotGrid: '#dbeee6',
    },
  },
  {
    id: 'neon', name: 'Neon', mode: 'dark',
    tokens: {
      bgBase: '#0d0d0d', bgSurface: '#16162a', bgPanel: '#0d0d0d',
      bgRaised: '#252545', bgHover: '#2f2f55',
      border: '#2a2a4a', borderLight: '#3a3a6a',
      accent: '#ff006e', accentHover: '#ff4d94',
      accentContrast: '#ffffff', accentText: '#ff5c9d',
      textPrimary: '#eaeaea', textSecondary: '#b0b0c0',
      textMuted: '#7a7a95', textFaint: '#55556e',
      danger: '#ff5470', success: '#00f5d4', warning: '#fee440',
      plotPaper: '#0d0d0d', plotBg: '#0d0d0d', plotGrid: '#2a2a4a',
    },
  },
]

const STORAGE_KEY = 'dspkit-theme'
const DEFAULT_ID = 'daylight'

export function themeById(id) {
  return THEMES.find(t => t.id === id) ?? THEMES[0]
}

/**
 * Reactive theme state. `custom` holds optional per-user plot overrides that
 * layer on top of the active theme; null means "use the theme as defined".
 */
export const themeState = $state({
  id: DEFAULT_ID,
  custom: null, // { plotBg?, plotGrid?, series?: string[] }
})

/** Resolved plot colours for the current theme + overrides. */
export function plotTheme() {
  const t = themeById(themeState.id)
  const c = themeState.custom ?? {}
  const base = t.mode === 'light' ? SERIES_LIGHT : SERIES_DARK
  return {
    paper:  c.plotBg   ?? t.tokens.plotPaper,
    bg:     c.plotBg   ?? t.tokens.plotBg,
    grid:   c.plotGrid ?? t.tokens.plotGrid,
    text:   t.tokens.textSecondary,
    title:  t.tokens.accentText,
    legend: t.tokens.bgSurface,
    border: t.tokens.border,
    danger: t.tokens.danger,
    warning: t.tokens.warning,
    series: c.series?.length ? c.series : base,
    mode:   t.mode,
  }
}

function kebab(key) {
  return key.replace(/[A-Z]/g, m => '-' + m.toLowerCase())
}

/** Write the active theme's tokens onto <html> and persist the choice. */
export function applyTheme() {
  const t = themeById(themeState.id)
  const root = document.documentElement
  root.setAttribute('data-theme', t.id)
  root.style.colorScheme = t.mode
  for (const [k, v] of Object.entries(t.tokens)) {
    root.style.setProperty(`--${kebab(k)}`, v)
  }
  // Custom plot overrides win over the theme's own plot tokens.
  const c = themeState.custom ?? {}
  if (c.plotBg)   { root.style.setProperty('--plot-bg', c.plotBg); root.style.setProperty('--plot-paper', c.plotBg) }
  if (c.plotGrid) root.style.setProperty('--plot-grid', c.plotGrid)

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: themeState.id, custom: themeState.custom }))
  } catch { /* private mode — theme just won't persist */ }
}

export function setTheme(id) {
  themeState.id = id
  themeState.custom = null
  applyTheme()
}

export function setCustom(patch) {
  themeState.custom = { ...(themeState.custom ?? {}), ...patch }
  applyTheme()
}

/** Restore the saved theme. Call once, before first paint. */
export function initTheme() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      if (saved?.id && THEMES.some(t => t.id === saved.id)) themeState.id = saved.id
      if (saved?.custom) themeState.custom = saved.custom
    }
  } catch { /* fall through to default */ }
  applyTheme()
}
