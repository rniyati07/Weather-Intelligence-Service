import { Link } from 'react-router'

import { SectionTitle } from '@/components/common/SectionTitle'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/constants/routes'
import { AiRole } from '../components/AiRole'
import { BuildProvenance } from '../components/BuildProvenance'
import { ConfidenceScale } from '../components/ConfidenceScale'
import { DecisionPipeline } from '../components/DecisionPipeline'
import { Limitations } from '../components/Limitations'

/**
 * About — `/about`. FDS §5.7.
 *
 * This page carries the product's honesty burden: how a verdict is computed,
 * what the confidence value means, what the AI is and is not allowed to do, and
 * what the product cannot tell you.
 *
 * Ordered by what a sceptical reader asks first — "where does this number come
 * from", then "did a chatbot write it", then "when should I not trust it".
 * Composition only; each section owns its own content.
 */
export function AboutPage() {
  return (
    <PageContainer
      // Same measured column as Settings: this is a reading page, and the
      // 1280px product width would run the prose past a comfortable measure.
      width="full"
      className="max-w-[52rem]"
      title="How this works"
      description="A verdict is computed, not guessed. Here is what goes into one, and where it stops."
    >
      <div className="flex flex-col gap-14">
        <section className="flex flex-col gap-5">
          <SectionTitle>How a verdict is made</SectionTitle>
          <DecisionPipeline />
        </section>

        <section className="flex flex-col gap-5">
          <SectionTitle>The role of AI</SectionTitle>
          <AiRole />
        </section>

        <section className="flex flex-col gap-5">
          <SectionTitle>How sure the result is</SectionTitle>
          <ConfidenceScale />
        </section>

        <section className="flex flex-col gap-5">
          <SectionTitle>What it cannot do</SectionTitle>
          <Limitations />
        </section>

        <section className="flex flex-col gap-5">
          <SectionTitle>Versions and data</SectionTitle>
          <BuildProvenance />
        </section>

        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-8">
          <Button variant="accent" size="lg" asChild>
            <Link to={ROUTES.plan}>Plan a trip</Link>
          </Button>
          <Button variant="ghost" size="lg" asChild>
            <Link to={ROUTES.home}>Back to start</Link>
          </Button>
        </div>
      </div>
    </PageContainer>
  )
}
