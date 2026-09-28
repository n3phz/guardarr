export const colors = {
  // Backgrounds
  bgDeep: '#050b16',
  bgPanel: '#0b1424',
  bgPanelHover: '#0c1a2d',
  bgCard: '#0c1a2d',
  bgCardBorder: '#1a2a44',

  // Text
  textPrimary: '#dce8f5',
  textSecondary: '#8fa4ba',
  textMuted: '#668099',
  textDim: '#4a5a7a',

  // Accents
  cyan: '#22d3ee',
  cyanBright: '#20bfff',
  cyanDim: '#0b5cff',
  blue: '#1d8cff',
  blueDim: '#0b5cff',
  gold: '#f59e0b',
  goldBright: '#fbbf24',
  green: '#34d399',
  greenBright: '#22c55e',
  red: '#ef4444',
  redBright: '#f87171',

  // State colors
  stateNormal: '#34d399',
  stateWarning: '#f59e0b',
  stateBlocked: '#ef4444',
  stateEmergency: '#f97316',
  stateCritical: '#dc2626',

  // Status colors
  statusConnected: '#34d399',
  statusDegraded: '#f59e0b',
  statusOffline: '#ef4444',
} as const

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
} as const

export const borderRadius = {
  sm: '4px',
  md: '8px',
  lg: '12px',
  xl: '20px',
} as const

export const fontSize = {
  xs: '0.6875rem',  // 11px
  sm: '0.75rem',    // 12px
  md: '0.875rem',   // 14px
  lg: '1rem',       // 16px
  xl: '1.125rem',   // 18px
  '2xl': '1.5rem',  // 24px
  '3xl': '2rem',    // 32px
} as const

export const fontFamily = {
  ui: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  mono: '"JetBrains Mono", "Fira Code", "SF Mono", monospace',
} as const

export const shadows = {
  sm: '0 1px 2px rgba(0, 0, 0, 0.3)',
  md: '0 4px 8px rgba(0, 0, 0, 0.4)',
  lg: '0 8px 24px rgba(0, 0, 0, 0.5)',
  glow: '0 0 20px rgba(34, 211, 238, 0.15)',
} as const

export const transitions = {
  fast: '125ms ease',
  normal: '200ms ease',
  slow: '300ms ease',
} as const

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
} as const

export const zIndex = {
  header: 100,
  sidebar: 200,
  modal: 300,
  tooltip: 400,
} as const