/** Theme values come from the mockup; see DESIGN_TOKENS.md. */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    screens: { sm: '640px', md: '768px', lg: '1024px', xl: '1280px' },
    extend: {
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'] },
      colors: {
        brand: { 50: '#eef0ff', 100: '#e2e5ff', 200: '#c9ceff', 500: '#5b5ef0', 600: '#4f46e5', 700: '#4338ca' },
        nav: { bg: '#0c1131', card: '#151b3f', line: '#252c5c', active: '#272f6e', text: '#c3c9e6', muted: '#7d86b8', accent: '#6366f1' },
        ink: { DEFAULT: '#0f1330', body: '#4b5272', muted: '#8a90ab', faint: '#aab0c6' },
        page: '#f7f8fc',
        line: '#e6e8f2',
        risk: {
          highBg: '#fdecec', highText: '#c62828', highLine: '#f6c9c9',
          medBg: '#fff6dc', medText: '#a16207', medLine: '#f1dd9b',
          lowBg: '#e8f8ee', lowText: '#15803d', lowLine: '#bde5cb',
          noneBg: '#f1f2f7', noneText: '#5b6280', noneLine: '#dde0ec',
        },
        ok: { bg: '#effaf3', line: '#b7e8c8', text: '#14532d' },
        info: { bg: '#eef4ff', line: '#c7dafe', text: '#1e3a8a' },
        ai: { bg: '#f6f3ff', line: '#e0d8ff', title: '#6d28d9', text: '#5b3fd0' },
        hit: { bg: '#fee2e2', text: '#b91c1c' },
      },
      borderRadius: { card: '14px', ctl: '10px' },
      boxShadow: { card: '0 1px 2px rgba(15,19,48,.04), 0 4px 14px rgba(15,19,48,.04)' },
      letterSpacing: { label: '0.08em' },
    },
  },
  plugins: [],
}
