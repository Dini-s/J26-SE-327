import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// the first render after a cold start can be slow on a synced folder
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})

// jsdom has no scrollIntoView
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => undefined
