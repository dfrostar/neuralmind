import Link from 'next/link';
import Logo from '@/components/ui/Logo';

// Twelve links in one undifferentiated wrapped row, every one of them carrying
// target="_blank" — so /privacy, /terms, /pricing, /services and /team, all
// pages on this same site, each opened a new tab. Grouped into columns, and
// only genuinely external destinations open away from the site.
const groups: { heading: string; links: { label: string; href: string }[] }[] = [
    {
        heading: 'Product',
        links: [
            { label: 'Pricing', href: '/pricing' },
            { label: 'Services', href: '/services' },
            { label: 'Team', href: '/team' },
            { label: 'Security', href: '/security' },
        ],
    },
    {
        heading: 'Developers',
        links: [
            { label: 'Docs', href: 'https://docs.neuralmind.uk/wiki/Home' },
            { label: 'GitHub', href: 'https://github.com/dfrostar/neuralmind' },
            { label: 'PyPI', href: 'https://pypi.org/project/neuralmind/' },
            { label: 'Release Notes', href: 'https://github.com/dfrostar/neuralmind/tree/main/docs/releases' },
        ],
    },
    {
        heading: 'Legal',
        links: [
            { label: 'License (MIT)', href: 'https://github.com/dfrostar/neuralmind/blob/main/LICENSE' },
            { label: 'Privacy', href: '/privacy' },
            { label: 'Terms', href: '/terms' },
            { label: 'Contact', href: 'mailto:hello@neuralmind.uk' },
        ],
    },
];

const isExternal = (href: string) => href.startsWith('http');

export default function Footer() {
    return (
        <footer className="border-t border-carbon-border pt-14 pb-10 px-4 md:px-6">
            <div className="max-w-6xl mx-auto">
                <div className="grid gap-10 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
                    <div>
                        <Link href="/" className="inline-flex items-center gap-2.5 mb-4">
                            <Logo className="w-[1.5rem] h-[1.5rem] text-electric" />
                            <span className="font-display font-semibold text-base tracking-tight text-white">
                                NeuralMind
                            </span>
                        </Link>
                        <p className="text-faint text-sm leading-relaxed max-w-xs">
                            Persistent memory and semantic code intelligence for AI coding agents.
                            Local-first, no telemetry.
                        </p>
                    </div>

                    {groups.map((group) => (
                        <nav key={group.heading} aria-label={group.heading}>
                            <h2 className="eyebrow mb-4">{group.heading}</h2>
                            <ul className="space-y-2.5">
                                {group.links.map((link) => (
                                    <li key={link.label}>
                                        <a
                                            href={link.href}
                                            className="text-slate-400 hover:text-white transition-colors text-sm"
                                            {...(isExternal(link.href)
                                                ? { target: '_blank', rel: 'noopener noreferrer' }
                                                : {})}
                                        >
                                            {link.label}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </nav>
                    ))}
                </div>

                <div className="rule mt-12 mb-6" />

                <p className="text-faint text-sm">2025–2026 Darren Frost · MIT License</p>
            </div>
        </footer>
    );
}
