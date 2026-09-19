import { Link } from 'react-router'

import { Container } from '@/components/common/Container'
import { APP_DESCRIPTION, APP_NAME } from '@/constants/app'
import { ROUTES } from '@/constants/routes'
import { env } from '@/lib/env'

export interface FooterProps {
  /**
   * `metadata.ruleConfigVersion` from the most recent response. Provenance: it
   * says which version of the rule engine produced the numbers on screen.
   */
  ruleConfigVersion?: string | null
}

/**
 * Footer — FDS §6.1.
 *
 * Three columns at `md` and above, stacked below. Carries the app version and
 * rule-config version, plus the operator link to provider status.
 *
 * That operator link is deliberately discreet and deliberately *not* in the
 * consumer navigation (FDS §4.3): `/status` is the only screen where provider
 * names may legitimately appear, and it requires an operator key.
 */
export function Footer({ ruleConfigVersion }: FooterProps) {
  return (
    <footer className="mt-20 border-t border-border py-10">
      <Container className="grid gap-8 md:grid-cols-3">
        <div className="flex flex-col gap-2">
          <p className="text-h4 font-semibold text-heading">{APP_NAME}</p>
          <p className="max-w-[42ch] text-body-sm text-muted-foreground">{APP_DESCRIPTION}</p>
        </div>

        <nav aria-label="Footer" className="flex flex-col gap-2">
          <FooterLink to={ROUTES.about}>About</FooterLink>
          <FooterLink to={ROUTES.settings}>Settings</FooterLink>
          <FooterLink to={ROUTES.plan}>Plan a trip</FooterLink>
        </nav>

        <div className="flex flex-col gap-2 md:items-end">
          <p className="tabular text-body-sm text-muted-foreground">
            App v{env.appVersion}
            {ruleConfigVersion ? ` · rules ${ruleConfigVersion}` : null}
          </p>
        </div>
      </Container>
    </footer>
  )
}

function FooterLink({ to, children }: { to: string; children: string }) {
  return (
    <Link
      to={to}
      // `min-h-8` keeps these stacked links above the 24px minimum target size
      // without visibly loosening the footer column.
      className="inline-flex min-h-8 w-fit items-center rounded-sm text-body-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {children}
    </Link>
  )
}
