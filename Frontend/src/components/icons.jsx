// Inline SVG icons so the app has no icon-font or icon-library dependency.
const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export const MenuIcon = () => (
  <svg {...base}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </svg>
)

export const PlusIcon = () => (
  <svg {...base}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const TrashIcon = () => (
  <svg {...base} width={16} height={16}>
    <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
  </svg>
)

export const SunIcon = () => (
  <svg {...base}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
)

export const MoonIcon = () => (
  <svg {...base}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
)

export const ArrowUpIcon = () => (
  <svg {...base} strokeWidth={2.5}>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </svg>
)

export const StopIcon = () => (
  <svg {...base} fill="currentColor" stroke="none">
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </svg>
)

export const BotIcon = () => (
  <svg {...base} width={20} height={20}>
    <rect x="4" y="7" width="16" height="12" rx="3" />
    <path d="M12 3v4M8 12h.01M16 12h.01M9 16h6" />
  </svg>
)

export const SparkIcon = () => (
  <svg {...base} width={28} height={28} strokeWidth={1.6}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
  </svg>
)

/** Chevron for the run bar and its command rows; rotated with CSS when open. */
export const ChevronIcon = () => (
  <svg {...base} width={14} height={14} strokeWidth={2.2}>
    <path d="m9 6 6 6-6 6" />
  </svg>
)

/** Marks the run bar: these are commands, not prose. */
export const CodeIcon = () => (
  <svg {...base} width={15} height={15}>
    <path d="M8 6 4 12l4 6" />
    <path d="m16 6 4 6-4 6" />
  </svg>
)

export const CheckIcon = () => (
  <svg {...base} width={14} height={14} strokeWidth={2.6}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

export const CrossIcon = () => (
  <svg {...base} width={14} height={14} strokeWidth={2.6}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
)

/** An open arc that reads as motion once the CSS spins it. */
export const SpinnerIcon = () => (
  <svg {...base} width={15} height={15} strokeWidth={2.4}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </svg>
)

export const PaperclipIcon = () => (
  <svg {...base} strokeWidth={1.8}>
    <path d="M21 12.5 12.5 21a5 5 0 0 1-7-7l8-8a3.5 3.5 0 1 1 5 5l-8 8a2 2 0 0 1-3-3l7.5-7.5" />
  </svg>
)

export const ImageIcon = () => (
  <svg {...base} strokeWidth={1.8}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="8.5" cy="9.5" r="1.5" />
    <path d="m21 16-5-5L5 20" />
  </svg>
)

export const XIcon = () => (
  <svg {...base} width={13} height={13} strokeWidth={2.4}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
)
