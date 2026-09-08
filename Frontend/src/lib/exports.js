// Links to files written by `snow.py export`.
//
// The assistant prints an absolute backend URL (http://127.0.0.1:8095/exports/x.pdf)
// because that is what the CLI knows. The browser may not be able to reach that
// host at all - the UI is often opened through a tunnel - so links are rewritten
// to this origin's /api proxy, which already forwards to the backend.

const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/+$/, '')

const EXPORT_PATH = /\/exports\/([^/?#]+)$/

export function isExportUrl(url) {
  const match = EXPORT_PATH.exec(url)
  if (!match) return false
  return /\.(xlsx|pdf|csv)$/i.test(match[1])
}

/** The same file, addressed through the proxy this page can actually reach. */
export function exportHref(url) {
  const match = EXPORT_PATH.exec(url)
  return match ? `${API_BASE}/exports/${match[1]}` : url
}

/** { name, format } for display on a download chip. */
export function exportLabel(url) {
  const match = EXPORT_PATH.exec(url)
  const name = match ? decodeURIComponent(match[1]) : url
  const dot = name.lastIndexOf('.')
  return {
    name,
    format: dot === -1 ? 'file' : name.slice(dot + 1).toLowerCase(),
  }
}
