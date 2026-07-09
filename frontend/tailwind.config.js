/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        page: '#F4F6F3',
        ink: '#1F3D2B',
        'ink-soft': '#55635A',
        sage: '#2F5D3A',
        'sage-mid': '#3A7D44',
        'sage-bg': '#E3ECE4',
        'sage-line': '#C5D0C6',
        muted: '#8A968C',
        card: '#FFFFFF',
      },
    },
  },
  plugins: [],
}
