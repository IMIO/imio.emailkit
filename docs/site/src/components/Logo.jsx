import clsx from 'clsx'
import Image from 'next/image'

import imioMark from '@/images/imio-mark.svg'

// The iMio constellation mark is magenta-only, and magenta reads correctly on
// both the white and the zinc-900 background — so there is no dark-mode variant
// to swap. It stays a static asset rather than inline paths because it is ~90 of
// them; `unoptimized` because a static export has no image optimiser.
export function Logo({ className, ...props }) {
  return (
    <span className={clsx('flex items-center gap-2.5', className)} {...props}>
      <Image
        src={imioMark}
        alt=""
        aria-hidden="true"
        className="w-6 flex-none"
        unoptimized
      />
      <span className="font-display text-base font-semibold tracking-tight whitespace-nowrap text-zinc-900 dark:text-white">
        imio<span className="text-accent-500">.</span>emailkit
      </span>
    </span>
  )
}
