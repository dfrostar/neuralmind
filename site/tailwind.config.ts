/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
        './src/components/**/*.{js,ts,jsx,tsx,mdx}',
        './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            colors: {
                carbon: '#070b15',
                'carbon-raised': '#0c1322',
                'carbon-card': '#0e1626',
                'carbon-border': '#1b2740',
                electric: '#3b82f6',
                'electric-bright': '#60a5fa',
                proton: '#a855f7',
                iris: '#8b5cf6',
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
                display: ['Fraunces', 'serif'],
            },
            animation: {
                'fade-in': 'fadeIn 0.8s ease-out',
                'fade-up': 'fadeUp 0.6s ease-out',
                'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
                'slide-up': 'slideUp 0.6s ease-out',
                'tag-roll': 'tagRoll 0.5s ease-out',
                'sparkle': 'sparkle 1.5s ease-in-out infinite',
                'ping-slow': 'ping 3s cubic-bezier(0, 0, 0.2, 1) infinite',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                fadeUp: {
                    '0%': { opacity: '0', transform: 'translateY(16px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                pulseGlow: {
                    '0%, 100%': { boxShadow: '0 0 0 0 rgba(96, 165, 250, 0.3)' },
                    '50%': { boxShadow: '0 0 30px 5px rgba(96, 165, 250, 0.4)' },
                },
                slideUp: {
                    '0%': { opacity: '0', transform: 'translateY(24px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                tagRoll: {
                    '0%': { opacity: '0', transform: 'translateY(20px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                sparkle: {
                    '0%, 100%': { opacity: '0.4' },
                    '50%': { opacity: '1' },
                },
            },
        },
    },
    plugins: [],
};
