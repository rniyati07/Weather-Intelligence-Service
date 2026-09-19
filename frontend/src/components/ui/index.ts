/**
 * UI primitives.
 *
 * Zero domain knowledge by rule: a component here must be usable in any app.
 * The moment one of these needs to know what a "risk level" is, it belongs in
 * `components/cards` or a feature module instead.
 */

export { Badge, type BadgeProps } from './badge'
export { Button, type ButtonProps } from './button'
export {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  type CardProps,
} from './card'
export { Input, Label, type InputProps } from './input'
export { Modal, ModalClose, ModalContent, ModalTrigger, type ModalContentProps } from './modal'
export { Divider, Separator, type SeparatorProps } from './separator'
export { Skeleton, SkeletonText } from './skeleton'
export { Spinner, type SpinnerProps } from './spinner'
export { Tooltip, TooltipContent, TooltipProvider, TooltipRoot, TooltipTrigger } from './tooltip'
export { badgeVariants, buttonVariants, cardVariants } from './variants'
