import { createElement } from 'react'

export default function CollapsibleSection({ title, children }) {
  return createElement(
    'details',
    { className: 'collapsible-section', open: true },
    createElement(
      'summary',
      { className: 'collapsible-section__summary' },
      createElement('span', { className: 'collapsible-section__chevron', 'aria-hidden': 'true' }, '›'),
      createElement('span', null, title),
    ),
    createElement('div', { className: 'collapsible-section__content' }, children),
  )
}
