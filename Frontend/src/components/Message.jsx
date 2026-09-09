import { useState } from 'react'
import ToolResult from './ToolResult.jsx'
import TypingIndicator from './TypingIndicator.jsx'
import RichText from './RichText.jsx'
import {
  BotIcon,
  CheckIcon,
  ChevronIcon,
  CodeIcon,
  CrossIcon,
  ImageIcon,
  PaperclipIcon,
  SpinnerIcon,
} from './icons.jsx'

export default function Message({ message, onFollowUp }) {
  const { role, text, pending, payload, tool, fields, mode, steps = [] } = message

  if (role === 'user') {
    const files = message.attachments || []
    return (
      <div className="msg msg-user">
        <div className="bubble">
          {text || <span className="dim">(attachment only)</span>}
          {files.length > 0 && (
            <div className="bubble-files">
              {files.map((file) => (
                <span key={file.id || file} className="bubble-file">
                  {file.kind === 'image' ? <ImageIcon /> : <PaperclipIcon />}
                  {file.name || 'attachment'}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="msg msg-assistant">
      <div className="avatar" aria-hidden="true" title="Answered from the ServiceNow REST API">
        <BotIcon />
      </div>
      <div className="msg-body">
        {mode === 'ai' && steps.length > 0 && <Steps steps={steps} />}
        {pending ? (
          <TypingIndicator />
        ) : (
          <>
            <RichText text={text} />
            {payload && <ToolResult tool={tool} payload={payload} fields={fields} onFollowUp={onFollowUp} />}
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Split `cd "..." && python snow.py query incident -f "..."` into the
 * subcommand and its arguments, so a row can lead with what was actually done
 * instead of 400 characters of boilerplate.
 */
function splitCommand(command) {
  const bare = String(command || '')
    .replace(/^\s*cd\s+("[^"]*"|'[^']*'|\S+)\s*&&\s*/, '')
    .replace(/^\s*(?:python|py|python3)\s+snow\.py\s*/, '')
    .trim()
  if (!bare) return { verb: 'snow.py', rest: '' }
  const cut = bare.indexOf(' ')
  return cut === -1 ? { verb: bare, rest: '' } : { verb: bare.slice(0, cut), rest: bare.slice(cut + 1) }
}

/**
 * The commands Claude ran, behind one "Ran N commands" row.
 *
 * Every command used to render as its own always-open block, so a single long
 * write buried the answer the user actually asked for. Now the whole run
 * collapses into one line; failures are counted on that line so a refused
 * command cannot hide behind a closed dropdown.
 */
function Steps({ steps }) {
  const [open, setOpen] = useState(false)
  const [openCommand, setOpenCommand] = useState(null)

  const tools = steps.filter((s) => s.kind === 'tool')
  const status = steps.filter((s) => s.kind === 'status').pop()

  // Before the first command there is nothing to summarise - show the status.
  if (tools.length === 0) {
    return status ? <p className="step-status">{status.text}</p> : null
  }

  const running = tools.filter((s) => s.status === 'running')
  const failed = tools.filter((s) => s.status === 'error').length
  const isRunning = running.length > 0
  const current = isRunning ? splitCommand(running[running.length - 1].command) : null

  const headline = isRunning
    ? `Running snow.py ${current.verb}`.trim()
    : `Ran ${tools.length} command${tools.length === 1 ? '' : 's'}`

  return (
    <div className="run">
      <button
        type="button"
        className="run-bar"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={`run-icon${isRunning ? ' run-icon-spin' : ''}`}>
          {isRunning ? <SpinnerIcon /> : <CodeIcon />}
        </span>
        <span className="run-headline">{headline}</span>
        {failed > 0 && <span className="run-failed">{failed} failed</span>}
        <span className={`run-chevron${open ? ' is-open' : ''}`}>
          <ChevronIcon />
        </span>
      </button>

      {open && (
        <ol className="cmd-list">
          {tools.map((step, i) => {
            const { verb, rest } = splitCommand(step.command)
            const isOpen = openCommand === (step.id || i)
            return (
              <li key={step.id || i} className="cmd">
                <button
                  type="button"
                  className="cmd-row"
                  aria-expanded={isOpen}
                  title={step.command}
                  onClick={() => setOpenCommand(isOpen ? null : step.id || i)}
                >
                  <span className={`cmd-status cmd-${step.status}`}>
                    {step.status === 'ok' && <CheckIcon />}
                    {step.status === 'error' && <CrossIcon />}
                    {step.status === 'running' && (
                      <span className="run-icon-spin">
                        <SpinnerIcon />
                      </span>
                    )}
                  </span>
                  <span className="cmd-verb">{verb}</span>
                  <span className="cmd-rest mono">{rest}</span>
                  <span className={`run-chevron${isOpen ? ' is-open' : ''}`}>
                    <ChevronIcon />
                  </span>
                </button>
                {isOpen && (
                  <div className="cmd-detail">
                    {/* The row truncates; the full command belongs here, wrapped. */}
                    <pre className="cmd-full mono">{step.command}</pre>
                    {step.result ? (
                      <pre className="note-text">{step.result}</pre>
                    ) : (
                      <p className="step-status">
                        {step.status === 'running' ? 'Still running...' : 'No output.'}
                      </p>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}
