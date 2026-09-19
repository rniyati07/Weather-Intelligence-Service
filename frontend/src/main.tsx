import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import '@/styles/globals.css'

const container = document.getElementById('root')

// A non-null assertion here would turn a missing root into a confusing
// "Cannot read properties of null" further down the stack.
if (!container) {
  throw new Error('Root element #root was not found in index.html.')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
