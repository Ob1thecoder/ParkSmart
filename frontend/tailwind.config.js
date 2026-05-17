/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Syne", "system-ui", "sans-serif"],
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        park: {
          ink: "#0c1a14",
          mist: "#e8f2ec",
          fern: "#1f6b4a",
          amber: "#c9780a",
          brick: "#b4232c",
          slate: "#5c6f66",
        },
        warm: "#faf9f6",
        greeting: "#f0f8f3",
      },
      boxShadow: {
        sheet: "0 -8px 40px rgba(12, 26, 20, 0.12)",
        drawer: "-4px 0 32px rgba(12, 26, 20, 0.08)",
        subtle: "0 1px 4px rgba(0, 0, 0, 0.04)",
      },
      animation: {
        "dot-jump": "dot-jump 1.2s ease-in-out infinite",
        "live-pulse": "live-pulse 1.9s ease-in-out infinite",
        "slide-in": "slide-in 0.16s ease-out",
        "ps-shimmer": "ps-shimmer 1.5s ease-in-out infinite",
        "ps-bar-slide": "ps-bar-slide 1.4s ease-in-out infinite",
        "ps-live-pulse": "ps-live-pulse 1.9s ease-out infinite",
      },
    },
  },
  plugins: [],
};
