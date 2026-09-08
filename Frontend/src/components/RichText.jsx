// Small renderer for assistant prose: paragraphs, "- " bullets, "1." numbered
// lists, "#" headings, markdown tables, ``` code blocks, **bold**, `code` and
// links. Deliberately not a full Markdown engine - just the shapes the
// assistant is told to use.
import { exportHref, exportLabel, isExportUrl } from '../lib/exports.js'

const TABLE_ROW = /^\s*\|(.+)\|\s*$/
// | --- | :--- | ---: | the separator under a table's header row
const TABLE_RULE = /^\s*\|[\s:|-]+\|\s*$/
const FENCE = /^\s*```(\w*)\s*$/

function cells(line) {
  return line
    .replace(/^\s*\|/, '')
    .replace(/\|\s*$/, '')
    .split('|')
    .map((c) => c.trim())
}

function parse(text) {
  const lines = text.split('\n')
  const blocks = []
  let list = null
  let i = 0

  while (i < lines.length) {
    const raw = lines[i]
    const line = raw.replace(/\s+$/, '')

    // ``` fenced code: take everything up to the closing fence verbatim.
    const fence = line.match(FENCE)
    if (fence) {
      const code = []
      i += 1
      while (i < lines.length && !FENCE.test(lines[i])) {
        code.push(lines[i])
        i += 1
      }
      i += 1 // skip the closing fence
      blocks.push({ type: 'code', lang: fence[1] || '', text: code.join('\n') })
      list = null
      continue
    }

    // A table needs a header row and the |---|---| rule directly under it.
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1])) {
      const head = cells(line)
      const rows = []
      i += 2
      while (i < lines.length && TABLE_ROW.test(lines[i]) && !TABLE_RULE.test(lines[i])) {
        rows.push(cells(lines[i]))
        i += 1
      }
      blocks.push({ type: 'table', head, rows })
      list = null
      continue
    }

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
    i += 1
  }
  return blocks
}

export default function RichText({ text }) {
  if (!text) return null
  return (
    <div className="rich">
      {parse(text).map((block, i) => {
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
        if (block.type === 'code') {
          return (
            <pre key={i} className="rich-code" data-lang={block.lang || undefined}>
              <code>{block.text}</code>
            </pre>
          )
        }
        if (block.type === 'table') {
          return (
            // Wrapped so a wide table scrolls inside the bubble instead of
            // stretching it past the width of the conversation.
            <div key={i} className="rich-table-wrap">
              <table className="rich-table">
                <thead>
                  <tr>
                    {block.head.map((h, j) => (
                      <th key={j}>{inline(h)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, j) => (
                    <tr key={j}>
                      {block.head.map((_, k) => (
                        <td key={k}>{inline(row[k] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
  return String(s).split(INLINE).map((part, i) => {
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
