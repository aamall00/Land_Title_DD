/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        },
        risk: {
          low:      '#16a34a',
          medium:   '#d97706',
          high:     '#dc2626',
          critical: '#7f1d1d',
        },
      },
      fontFamily: {
        kannada: ['"Noto Sans Kannada"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
