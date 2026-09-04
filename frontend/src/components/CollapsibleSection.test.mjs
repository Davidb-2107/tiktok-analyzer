import test from 'node:test'
import assert from 'node:assert/strict'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import CollapsibleSection from './CollapsibleSection.js'

test('renders an accessible titled section open by default', () => {
  const html = renderToStaticMarkup(
    createElement(
      CollapsibleSection,
      { title: 'Sampled frames' },
      createElement('p', null, 'frames'),
    ),
  )

  assert.match(html, /<details[^>]*class="collapsible-section"[^>]*open=""/)
  assert.match(html, /<summary[^>]*>.*Sampled frames/s)
  assert.match(html, /frames/)
})
