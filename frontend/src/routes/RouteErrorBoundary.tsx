import { isRouteErrorResponse, useNavigate, useRouteError } from 'react-router'

import { ErrorState } from '@/components/feedback/ErrorState'
import { PageContainer } from '@/components/layout/PageContainer'
import { getErrorPresentation } from '@/constants/error-copy'
import { ApiError } from '@/services/api'
import { ROUTES } from '@/constants/routes'

/**
 * Router-level error boundary.
 *
 * Catches anything a route throws — a loader rejection, a render crash — and
 * renders it as a page rather than a blank screen.
 *
 * The important detail is that an `ApiError` is presented through the same
 * `getErrorPresentation` map every other error state uses. That is what keeps
 * one error code producing one wording, wherever it surfaces, instead of the
 * boundary inventing its own copy that drifts from the rest of the product.
 */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()

  const goHome = () => void navigate(ROUTES.home)

  if (ApiError.is(error)) {
    const presentation = getErrorPresentation(error.code)

    return (
      <PageContainer width="prose">
        <ErrorState
          headline={presentation.headline}
          body={presentation.body}
          requestId={error.requestId}
          action={presentation.action ? { label: presentation.action, onClick: goHome } : undefined}
        />
      </PageContainer>
    )
  }

  if (isRouteErrorResponse(error)) {
    return (
      <PageContainer width="prose">
        <ErrorState
          headline={error.status === 404 ? "We couldn't find that page" : 'Something went wrong'}
          body={
            error.status === 404
              ? 'The link may be out of date, or the address may have a typo in it.'
              : 'An unexpected error occurred while loading this page.'
          }
          action={{ label: 'Go home', onClick: goHome }}
        />
      </PageContainer>
    )
  }

  return (
    <PageContainer width="prose">
      <ErrorState
        headline="Something went wrong"
        body="An unexpected error occurred. Reloading the page usually clears it."
        action={{ label: 'Go home', onClick: goHome }}
      />
    </PageContainer>
  )
}
