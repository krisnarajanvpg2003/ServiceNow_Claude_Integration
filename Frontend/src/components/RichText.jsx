// Small renderer for assistant prose: paragraphs, "- " bullets, "1." numbered
// lists, "#" headings, **bold**, `code` and links. Deliberately not a full
// Markdown engine.
import { exportHref, exportLabel, isExportUrl } from '../lib/exports.js'

export default function RichText({ text }) {
  if (!text) return null
  const blocks = []
  let list = null
  for (const rawLine of text.split('\n')) {
    const line = rawLine.replace(/\s+$/, '')
    const bullet = line.match(/^\s*[-•*]\s+(.*)$/)
    const numbered = line.match(/^\s*(\d+)[.)]\s+(.*)$/)
    const heading = line.match(/^\s*#{1,4}\s+(.*)$/)
    if (bullet || numbered) {
      const type = bullet ? 'ul' : 'ol'
      if (!list || list.type !== type) {
        list = { type, items: [] }
        blocks.push(list)
      }
      list.items.push(bullet ? bullet[1] : numbered[2])
    } else {
      list = null
      if (heading) blocks.push({ type: 'h', text: heading[1] })
      else if (line.trim()) blocks.push({ type: 'p', text: line })
    }
  }
  return (
    <div className="rich">
      {blocks.map((block, i) => {
        if (block.type === 'ul' || block.type === 'ol') {
          const Tag = block.type
          return (
            <Tag key={i}>
              {block.items.map((item, j) => (
                <li key={j}>{inline(item)}</li>
              ))}
            </Tag>
          )
        }
        if (block.type === 'h') return <p key={i} className="rich-heading">{inline(block.text)}</p>
        return <p key={i}>{inline(block.text)}</p>
      })}
    </div>
  )
}

// **bold**, `code`, and bare http(s) URLs. A trailing . , ) etc. is sentence
// punctuation rather than part of the link, so it is left outside the anchor.
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|https?:\/\/[^\s<>()"]+[^\s<>()".,;:!?])/g

function inline(s) {
  return s.split(INLINE).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>
    if (/^https?:\/\//.test(part)) return link(part, i)
    return part
  })
}

function link(url, key) {
  // An exported file gets a download chip, and is routed through this origin's
  // /api proxy so it also works when the UI is shared over a tunnel.
  if (isExportUrl(url)) {
    const { name, format } = exportLabel(url)
    return (
      <a key={key} className={`file-chip file-chip-${format}`} href={exportHref(url)} download={name}>
        <span className="file-chip-ext">{format}</span>
        <span className="file-chip-name">{name}</span>
        <span className="file-chip-action">Download</span>
      </a>
    )
  }
  return (
    <a key={key} href={url} target="_blank" rel="noopener noreferrer">
      {url}
    </a>
  )
}
