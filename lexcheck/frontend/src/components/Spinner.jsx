const SIZE_CLASS = {
  18: 'spinner--sm',
  32: 'spinner--md',
  36: 'spinner--lg',
}

export default function Spinner({ size = 18 }) {
  const sizeClass = SIZE_CLASS[size] || SIZE_CLASS[18]
  return <span className={`spinner ${sizeClass}`} aria-hidden />
}
