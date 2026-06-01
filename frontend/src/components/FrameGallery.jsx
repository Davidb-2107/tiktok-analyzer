import { useState } from 'react'

export default function FrameGallery({ frames }) {
  const [selected, setSelected] = useState(null)

  return (
    <>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: '0.75rem',
      }}>
        {frames.map((url, i) => (
          <img
            key={url}
            src={url}
            alt={`frame ${i + 1}`}
            onClick={() => setSelected(url)}
            style={{
              width: '100%',
              aspectRatio: '9/16',
              objectFit: 'cover',
              borderRadius: '8px',
              cursor: 'pointer',
              border: '2px solid transparent',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => e.target.style.borderColor = '#fe2c55'}
            onMouseLeave={e => e.target.style.borderColor = 'transparent'}
          />
        ))}
      </div>

      {selected && (
        <div
          onClick={() => setSelected(null)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 100, cursor: 'zoom-out',
          }}
        >
          <img
            src={selected}
            alt="full size"
            style={{ maxHeight: '90vh', maxWidth: '90vw', borderRadius: '8px' }}
          />
        </div>
      )}
    </>
  )
}
