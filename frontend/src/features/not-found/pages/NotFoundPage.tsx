import { Compass } from 'lucide-react'
import { useNavigate } from 'react-router'

import { PageContainer } from '@/components/layout/PageContainer'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/constants/routes'

/**
 * 404 — any unmatched route.
 *
 * Plain language, and a way forward. Uses `EmptyState` rather than `ErrorState`
 * on purpose: a mistyped URL is a wrong turn, not a failure, and it should not
 * be dressed in the red treatment reserved for things that actually broke.
 */
export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <PageContainer width="prose">
      <EmptyState
        icon={Compass}
        headline="We couldn't find that page"
        body="The link may be out of date, or the address may have a typo in it."
        action={{ label: 'Go home', onClick: () => void navigate(ROUTES.home) }}
      />

      <div className="mt-6 flex justify-center">
        <Button variant="ghost" size="sm" onClick={() => void navigate(ROUTES.plan)}>
          Plan a trip instead
        </Button>
      </div>
    </PageContainer>
  )
}
