import CollapsibleSection from './CollapsibleSection.js'

export default function Transcript({ text, title = 'Transcript' }) {
  return (
    <CollapsibleSection title={title}>
      <div style={{
        padding: '1rem 1.25rem',
        border: '1px solid #2a2a2a',
        borderTop: 'none',
        borderRadius: '0 0 8px 8px',
        background: '#141414',
      }}>
        {/* pre-line: overlay_text is one OCR caption per \n-separated line */}
        <p style={{ fontSize: '0.95rem', color: '#d0d0d0', lineHeight: 1.6, margin: 0, whiteSpace: 'pre-line' }}>
          {text}
        </p>
      </div>
    </CollapsibleSection>
  )
}
