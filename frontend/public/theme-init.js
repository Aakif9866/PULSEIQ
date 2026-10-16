// Runs before first paint (blocking, in <head>) so the page never flashes
// the wrong theme. Kept in a file, not inline: the CSP is script-src 'self'.
// The key must match THEME_KEY in src/lib/theme.ts.
;(function () {
  var t
  try {
    t = localStorage.getItem('pulseiq-theme')
  } catch {}
  if (t !== 'light' && t !== 'dark') {
    t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  document.documentElement.dataset.theme = t
})()
