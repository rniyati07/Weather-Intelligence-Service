/**
 * Markdown rendering for assistant replies.
 *
 * This is typography, not parsing: it only ever changes how text the backend
 * already returned *looks* — headings, bold spans, lists, tables, links — it
 * extracts no values and infers no structure the model did not already put
 * there. The rule this respects is `MessageBubble` renders only the message
 * content and never derives a fact from it (master prompt, "Message
 * Rendering"). GFM (tables, task lists, strikethrough) via `remark-gfm`,
 * since the response prompt explicitly asks the model for markdown tables
 * and day-by-day lists on a detailed answer — rendering them as their
 * intended structure instead of raw `| pipe | syntax |` is exactly the same
 * "typography, not parsing" contract, just no longer failing on constructs
 * the backend actually sends.
 *
 * One deliberate exception, and it isn't really one: `renderMessageText`
 * optionally takes this turn's own `places[]` and turns a place name that
 * appears verbatim in the text into a link to that same real place's Maps
 * location (`linkifyPlaceNames`). That's matching text against structured
 * data the backend already fetched for this exact turn — the same grounding
 * `PlaceList` already relies on — never inventing a name or a URL.
 *
 * No raw HTML passthrough (`rehype-raw` is deliberately not installed) —
 * assistant text renders as markdown only, never as arbitrary markup.
 */

import { Fragment, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { ChatPlace } from '@/types'
import { getPlaceMapsUrl } from '@/utils/places'

/**
 * Replace every verbatim occurrence of a known place's name inside plain-text
 * children with a link to that place's Maps location. Only ever touches
 * direct string children (and arrays of them) — an already-rendered element
 * child (e.g. a nested `<strong>`) is left alone rather than re-parsed, so
 * this can never double-wrap or fight another renderer's own markup.
 */
function linkifyPlaceNames(children: ReactNode, places: ChatPlace[]): ReactNode {
  if (places.length === 0) return children

  if (Array.isArray(children)) {
    return (children as ReactNode[]).map((child, index) => (
      <Fragment key={index}>{linkifyPlaceNames(child, places)}</Fragment>
    ))
  }

  if (typeof children !== 'string') return children

  // Longest name first, so a shorter place's name can't shadow a match that
  // should have gone to a longer one it happens to be a substring of.
  const byLength = [...places].sort((a, b) => b.name.length - a.name.length)

  const nodes: ReactNode[] = []
  let remaining = children
  let key = 0

  while (remaining.length > 0) {
    let best: { place: ChatPlace; index: number } | null = null
    for (const place of byLength) {
      if (!place.name) continue
      const index = remaining.indexOf(place.name)
      if (index !== -1 && (best === null || index < best.index)) {
        best = { place, index }
      }
    }

    if (!best) {
      nodes.push(remaining)
      break
    }

    if (best.index > 0) nodes.push(remaining.slice(0, best.index))
    nodes.push(
      <a
        key={`place-link-${String(key)}`}
        href={getPlaceMapsUrl(best.place)}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
      >
        {best.place.name}
      </a>,
    )
    key += 1
    remaining = remaining.slice(best.index + best.place.name.length)
  }

  return nodes
}

function buildComponents(places: ChatPlace[]): Components {
  const linkify = (children: ReactNode) => linkifyPlaceNames(children, places)

  return {
    p: ({ children }) => <p>{linkify(children)}</p>,
    strong: ({ children }) => (
      <strong className="font-semibold text-heading">{linkify(children)}</strong>
    ),
    em: ({ children }) => <em>{linkify(children)}</em>,

    h1: ({ children }) => (
      <h4 className="mt-4 mb-1 text-h4 font-semibold text-heading first:mt-0">{children}</h4>
    ),
    h2: ({ children }) => (
      <h4 className="mt-4 mb-1 text-h4 font-semibold text-heading first:mt-0">{children}</h4>
    ),
    h3: ({ children }) => (
      <h4 className="mt-3 mb-1 text-body-lg font-semibold text-heading first:mt-0">{children}</h4>
    ),

    ul: ({ children, className }) => (
      <ul
        className={
          // A GFM task list (`- [ ] item`) carries its own `className` from
          // remark-gfm — `list-none` so the checkbox is the only marker, no
          // bullet doubling up next to it. An ordinary list keeps the bullet.
          className?.includes('contains-task-list')
            ? 'my-2 flex list-none flex-col gap-1.5'
            : 'my-2 flex list-disc flex-col gap-1 pl-5'
        }
      >
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="my-2 flex list-decimal flex-col gap-1 pl-5">{children}</ol>
    ),
    li: ({ children, className }) => (
      <li
        className={
          className?.includes('task-list-item')
            ? 'flex items-start gap-2'
            : 'pl-1 marker:text-primary'
        }
      >
        {linkify(children)}
      </li>
    ),
    // The one native form control in the whole render path — always
    // `disabled` (react-markdown/remark-gfm marks a task-list checkbox
    // disabled by default), so this is a decorative reflection of what the
    // model wrote, never a control with state of its own. `accent-primary`
    // recolours the native box to the brand without needing a custom
    // replacement element.
    input: (props) =>
      props.type === 'checkbox' ? (
        <input {...props} disabled className="mt-1 size-4 shrink-0 accent-primary" />
      ) : (
        <input {...props} />
      ),

    hr: () => <hr className="my-4 border-border" />,

    // A callout for a tip or a watch-out the model is flagging inline — the
    // one other "element" GFM offers beyond tables/lists, styled as a quiet
    // insight-gold aside rather than a plain indent, matching the same
    // AI-generated-content cue the message avatar already carries.
    blockquote: ({ children }) => (
      <blockquote className="my-3 rounded-md border-l-4 border-ai-accent bg-ai-surface py-2 pr-3 pl-3 text-ai-foreground">
        {children}
      </blockquote>
    ),

    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-primary underline underline-offset-2 hover:text-primary-hover"
      >
        {children}
      </a>
    ),

    code: ({ children }) => (
      <code className="rounded-sm bg-muted px-1.5 py-0.5 text-body-sm">{children}</code>
    ),

    // Tables are the construct the old hand-rolled renderer dropped entirely —
    // a wrapping scroll container keeps a wide itinerary table from blowing
    // out the transcript column on a phone, matching how `DayStrip` already
    // handles its own horizontal overflow.
    table: ({ children }) => (
      <div className="my-3 overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-body-sm">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-primary-subtle">{children}</thead>,
    tbody: ({ children }) => <tbody className="divide-y divide-border">{children}</tbody>,
    tr: ({ children }) => <tr>{children}</tr>,
    th: ({ children }) => (
      <th className="px-3 py-2 text-left font-semibold whitespace-nowrap text-heading">
        {linkify(children)}
      </th>
    ),
    td: ({ children }) => <td className="px-3 py-2 align-top">{linkify(children)}</td>,
  }
}

/**
 * Render one assistant or user message as markdown, styled with the app's
 * own semantic tokens rather than react-markdown's unstyled defaults.
 *
 * `places`, when given, are this turn's own real places (`getMessagePlaces`)
 * — used only to turn a name already present in the text into a Maps link,
 * never to add a name that wasn't already there.
 */
export function renderMessageText(text: string, places: ChatPlace[] = []): ReactNode {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildComponents(places)}>
      {text}
    </ReactMarkdown>
  )
}
