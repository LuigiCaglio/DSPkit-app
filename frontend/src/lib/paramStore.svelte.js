// Analysis settings that outlive their control component.
//
// Each control lives in an {#if} branch of AnalysisPanel, so switching tabs
// unmounts it and its $state reverts to defaults. That was merely annoying
// before; with auto-run it means glancing at another tab and coming back
// silently recomputes at the default nperseg rather than the one you set.
//
// Module scope survives unmount, so settings are held here per analysis and
// handed back when the control returns.

const store = new Map()

/**
 * The persisted settings for `tab`, seeded from `defaults` the first time.
 *
 * Returns a reactive object: read it to initialise the control's own state,
 * and write back through `remember()` so a later mount picks it up.
 */
export function paramsFor(tab, defaults) {
  if (!store.has(tab)) {
    const kept = $state({ ...defaults })
    store.set(tab, kept)
  }
  return store.get(tab)
}

/** Copy the control's current values back into the store. */
export function remember(bag, values) {
  Object.assign(bag, values)
}

/** Forget everything — used when a new file makes old settings meaningless. */
export function resetParams() {
  store.clear()
}

/**
 * Every remembered setting, as plain data, for saving against a session.
 *
 * Module scope survives an unmount but not a reload, which is why this needs to
 * leave the module at all: the nperseg you settled on should come back with the
 * file it was chosen for.
 */
export function exportParams() {
  const out = {}
  for (const [tab, bag] of store) out[tab] = { ...bag }
  return out
}

/**
 * Seed the store from saved data.
 *
 * Merged into whatever a tab already holds rather than replacing the map, so a
 * control that mounted before the restore arrived still picks the values up —
 * `paramsFor` hands back the same object it was given.
 */
export function importParams(saved) {
  if (!saved || typeof saved !== 'object') return
  for (const [tab, values] of Object.entries(saved)) {
    if (!values || typeof values !== 'object') continue
    const existing = store.get(tab)
    if (existing) {
      Object.assign(existing, values)
    } else {
      const bag = $state({ ...values })
      store.set(tab, bag)
    }
  }
}
