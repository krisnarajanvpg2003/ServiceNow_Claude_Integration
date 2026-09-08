import ToolResult from './ToolResult.jsx'
import TypingIndicator from './TypingIndicator.jsx'
import RichText from './RichText.jsx'
import { BotIcon } from './icons.jsx'

export default function Message({ message, onFollowUp }) {
  const { role, text, pending, payload, tool, fields, mode, steps = [] } = message

  if (role === 'user') {
    return (
      <div className="msg msg-user">
        <div className="bubble">{text}</div>
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

/** The commands Claude ran, with their output collapsed behind a summary. */
function Steps({ steps }) {
  return (
    <ol className="steps">
      {steps.map((step, i) =>
        step.kind === 'tool' ? (
          <li key={step.id || i} className={`step-tool step-${step.status}`}>
            <details>
              <summary>
                <code className="mono">{step.command}</code>
                {step.status === 'running' && <span className="dim"> running...</span>}
                {step.status === 'error' && <span className="dim"> failed</span>}
              </summary>
              {step.result && <pre className="note-text">{step.result}</pre>}
            </details>
          </li>
        ) : (
          <li key={i} className="step-status">
            {step.text}
          </li>
        ),
      )}
    </ol>
  )
}
