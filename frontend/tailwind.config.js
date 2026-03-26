/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        arena: {
          bg:       "#0a0a0f",
          surface:  "#12121a",
          border:   "#1e1e2e",
          muted:    "#2a2a3a",
          text:     "#e2e8f0",
          subtle:   "#94a3b8",
          accent:   "#7c3aed",
          gold:     "#f59e0b",
          green:    "#10b981",
          red:      "#ef4444",
          blue:     "#3b82f6",
          orange:   "#f97316",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "fade-in":    "fadeIn 0.4s ease-out",
        "slide-up":   "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn:  { "0%": { opacity: 0 }, "100%": { opacity: 1 } },
        slideUp: { "0%": { transform: "translateY(8px)", opacity: 0 },
                   "100%": { transform: "translateY(0)", opacity: 1 } },
      },
    },
  },
  plugins: [],
};
