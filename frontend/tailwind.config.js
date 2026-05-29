/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "pai-bg": "#1a1a2e",
        "pai-card": "#16213e",
        "pai-accent": "#0f3460",
        "pai-highlight": "#e94560",
        "pai-text": "#eaeaea",
        "pai-muted": "#8b8b8b",
      },
    },
  },
  plugins: [],
};
