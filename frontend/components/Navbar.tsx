'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity } from 'lucide-react'

const links = [
  { href: '/',        label: 'Signals'     },
  { href: '/trades',  label: 'Trades'      },
  { href: '/pnl',    label: 'Performance'  },
  { href: '/chart',  label: 'Chart'        },
  { href: '/status', label: 'Status'       },
]

export default function Navbar() {
  const pathname = usePathname()
  return (
    <header className="sticky top-0 z-50 bg-black/80 backdrop-blur-md border-b border-gray-800">
      <div className="max-w-8xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8 h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 shrink-0">
            <Activity size={18} className="text-teal-400" />
            <span className="text-teal-400 font-bold text-base tracking-tight">
              TradingBot
            </span>
          </Link>

          {/* Nav links */}
          <nav className="flex items-center gap-1 overflow-x-auto scrollbar-none">
            {links.map(({ href, label }) => {
              const active = pathname === href
              return (
                <Link
                  key={href}
                  href={href}
                  className={`
                    relative px-3 py-1.5 text-sm font-medium rounded-lg
                    transition-colors duration-150 whitespace-nowrap
                    ${active
                      ? 'text-teal-400 bg-teal-400/10'
                      : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800/60'
                    }
                  `}
                >
                  {label}
                  {active && (
                    <span className="absolute bottom-0 left-3 right-3 h-0.5 bg-teal-400 rounded-full" />
                  )}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>
    </header>
  )
}
