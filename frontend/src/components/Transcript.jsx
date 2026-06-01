export default function Transcript({ text }) {
  return (
    <div style={{
      padding: '1rem 1.25rem',
      borderRadius: '8px',
      border: '1px solid #2a2a2a',
      background: '#141414',
    }}>
      <div style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Transcript
      </div>
      <p style={{ fontSize: '0.95rem', color: '#d0d0d0', lineHeight: 1.6, margin: 0 }}>
        {text}
      </p>
    </div>
  )
}
