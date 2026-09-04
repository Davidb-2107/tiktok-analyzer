import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const transcriptSource = readFileSync(new URL('./Transcript.jsx', import.meta.url), 'utf8')

test('Transcript is wired to the shared collapsible section', () => {
  assert.match(transcriptSource, /import CollapsibleSection from ['"]\.\/CollapsibleSection\.js['"]$/m)
  assert.match(transcriptSource, /<CollapsibleSection title=\{title\}>/)
  assert.match(transcriptSource, /<\/CollapsibleSection>/)
})
