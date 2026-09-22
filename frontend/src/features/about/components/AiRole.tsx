import { CloudSun } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { AI_PANEL_TITLE } from '@/constants/app'

/**
 * What the AI does, and what it does not — FDS §5.7, §1.3.
 *
 * The most important thing on this page. A reader who believes a language model
 * produced the verdict will discount it, and they would be right to; the value
 * of the product rests on the separation being real and legible.
 *
 * Deliberately **not** rendered on the insight-gold AI surface. That surface
 * means "this text was generated", and using it for a human-written
 * explanation *of* the AI would undermine the one visual convention this page
 * is defending.
 */
export function AiRole() {
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-4">
        <p className="text-body-lg text-foreground">
          The AI writes the explanation. It does not make the decision.
        </p>

        <p className="text-body text-muted-foreground">
          Risk levels, scores, rankings and packing lists are all computed before any model is
          involved. The finished result is then handed to a language model with a single job:
          restate it in readable prose. It cannot compute a value, change one, or reorder your days.
        </p>

        <p className="text-body text-muted-foreground">
          The conversational assistant works the same way. Every turn's weather figures come from
          the same deterministic engine, and every place it mentions — a beach, a museum, a
          restaurant — comes from a real places database, never from the model. The assistant is
          only ever asked to explain data that already exists; it is never asked to invent a place
          or a number to fill a gap.
        </p>

        <div className="flex flex-col gap-3 border-t border-border pt-4">
          <h3 className="flex items-center gap-2.5 text-h4 font-semibold text-heading">
            <CloudSun className="size-5 text-ai-accent" aria-hidden="true" />
            How you can tell them apart
          </h3>

          <ul className="flex flex-col gap-3 text-body text-muted-foreground">
            <li>
              Generated text sits on its own tinted surface, under the heading &ldquo;
              {AI_PANEL_TITLE}&rdquo; on a result page, or with a small assistant glyph in the
              conversation. Everything else is computed.
            </li>
            <li>
              No number, date or place name displayed anywhere is read out of generated text.
              Figures and places come from the structured result, so the prose cannot contradict the
              cards or references sitting beside it.
            </li>
            <li>
              If a result page's explanation fails to generate, the result stays exactly as it is
              and the rest of the page keeps working. In conversation, a model failure falls back to
              a plain structured summary of the same trusted data — you are never shown an error
              where a trip summary should be.
            </li>
          </ul>
        </div>
      </Card>

      <p className="text-body-sm text-subtle-foreground">
        The explanation is a convenience, not a source. Where the prose and the structured data seem
        to disagree, the structured data is correct.
      </p>
    </div>
  )
}
