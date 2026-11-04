/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: {
          app: '#0B0F17',
          sidebar: '#0E131F',
          surface: '#131B2E',
          elevated: '#1A243B',
          border: '#1E293B',
          borderHover: '#334155',
        },
        text: {
          primary: '#F1F5F9',
          secondary: '#94A3B8',
          muted: '#64748B',
        },
        accent: {
          DEFAULT: '#38BDF8',
          hover: '#0EA5E9',
          subtle: 'rgba(56, 189, 248, 0.10)',
          border: 'rgba(56, 189, 248, 0.28)',
        },
        status: {
          success: '#34D399',
          warning: '#FBBF24',
          danger: '#F87171',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      transitionDuration: {
        DEFAULT: '150ms',
        fast: '140ms',
        panel: '200ms',
      },
      transitionTimingFunction: {
        snappy: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
