import { cn } from '../utils/formatters'

interface StatusBadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'state' | 'integration' | 'threshold'
  color?: string
  className?: string
}

export function StatusBadge({ children, variant = 'default', color, className }: StatusBadgeProps) {
  const baseStyles = `
    inline-flex items-center px-2 py-0.5
    text-xs font-medium uppercase tracking-wider rounded-full
    transition-colors var(--transition-fast)
  `

  const variantStyles = {
    default: 'bg-opacity-10',
    state: 'bg-opacity-15 border border-opacity-30',
    integration: 'bg-opacity-15',
    threshold: 'bg-opacity-20 font-semibold px-3 py-1 text-sm',
  }

  return (
    <span
      className={cn(baseStyles, variantStyles[variant], className)}
      style={{ '--badge-color': color } as React.CSSProperties}
    >
      {children}
    </span>
  )
}