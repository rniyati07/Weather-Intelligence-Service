/**
 * A tiny, closed subset of markdown-lite rendering for assistant replies.
 *
 * This is typography, not parsing: it only ever changes how text the backend
 * already returned *looks* (paragraph breaks, bold spans) — it extracts no
 * values and infers no structure the model did not already put there. The
 * rule this respects is `MessageBubble` renders only the message content and
 * never derives a fact from it (master prompt, "Message Rendering").
 */

import { Fragment, type ReactNode } from 'react'

const BOLD_PATTERN = /\*\*(.+?)\*\*/g

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let index = 0
  BOLD_PATTERN.lastIndex = 0

  let match = BOLD_PATTERN.exec(text)
  while (match !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index))
    nodes.push(<strong key={`${keyPrefix}-${String(index)}`}>{match[1]}</strong>)
    lastIndex = BOLD_PATTERN.lastIndex
    index += 1
    match = BOLD_PATTERN.exec(text)
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex))

  return nodes
}

/**
 * Split on blank lines into paragraphs; a single newline within one becomes
 * a line break. `**bold**` spans render as `<strong>`. Nothing else is
 * interpreted.
 */
export function renderMessageText(text: string): ReactNode {
  const paragraphs = text.split(/\n{2,}/)

  return paragraphs.map((paragraph, paragraphIndex) => {
    const lines = paragraph.split('\n')
    return (
      <p key={`p-${String(paragraphIndex)}`}>
        {lines.map((line, lineIndex) => (
          <Fragment key={`l-${String(lineIndex)}`}>
            {lineIndex > 0 ? <br /> : null}
            {renderInline(line, `p${String(paragraphIndex)}l${String(lineIndex)}`)}
          </Fragment>
        ))}
      </p>
    )
  })
}
