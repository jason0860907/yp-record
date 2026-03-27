/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        accent: {
          DEFAULT: '#6366F1',
          light: '#818CF8',
          dark: '#4F46E5',
          glow: 'rgba(99, 102, 241, 0.2)',
        },
        speaker: {
          0: '#6366F1', // indigo
          1: '#059669', // emerald
          2: '#D97706', // amber
          3: '#E11D48', // rose
          4: '#7C3AED', // violet
        },
      },
      keyframes: {
        pulse_ring: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        'pulse-ring': 'pulse_ring 1.5s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
