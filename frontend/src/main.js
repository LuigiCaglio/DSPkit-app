import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { initTheme } from './lib/theme.svelte.js'

// Stamp the saved theme onto <html> before the first paint.
initTheme()

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
