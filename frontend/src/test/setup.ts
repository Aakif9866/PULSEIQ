import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// vitest.config.ts runs without `test.globals: true` (deliberately — see
// its comment), so @testing-library/react's own auto-cleanup, which
// detects a global `afterEach`, never fires on its own. Without this,
// every test in a file after the first renders on top of the previous
// test's still-mounted DOM.
afterEach(() => {
  cleanup()
})
