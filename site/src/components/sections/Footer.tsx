export default function Footer() {
    const links = [
        { label: 'Security', href: '/security' },
        { label: 'PyPI', href: 'https://pypi.org/project/neuralmind/' },
        { label: 'GitHub', href: 'https://github.com/dfrostar/neuralmind' },
        { label: 'Release Notes', href: 'https://github.com/dfrostar/neuralmind/tree/main/docs/releases' },
        { label: 'Docs', href: 'https://docs.neuralmind.uk/wiki/Home' },
        { label: 'Pricing', href: '/pricing' },
        { label: 'Team', href: '/team' },
        { label: 'License (MIT)', href: 'https://github.com/dfrostar/neuralmind/blob/main/LICENSE' },
        { label: 'Privacy', href: '/privacy' },
        { label: 'Terms', href: '/terms' },
        { label: 'Contact', href: 'mailto:hello@neuralmind.uk' },
    ];

    return (
        <footer className="border-t border-carbon-border/50 py-12 px-4 md:px-6">
            <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-electric to-proton flex items-center justify-center">
                        <span className="text-white font-display font-bold text-sm">N</span>
                    </div>
                    <span className="font-display font-bold text-lg text-white">
                        NeuralMind
                    </span>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-6 text-sm">
                    {links.map((link) => (
                        <a
                            key={link.label}
                            href={link.href}
                            className="text-slate-400 hover:text-white transition-colors"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            {link.label}
                        </a>
                    ))}
                </div>

                <p className="text-slate-500 text-sm">
                    2025–2026 Darren Frost · MIT License
                </p>
            </div>
        </footer>
    );
}
