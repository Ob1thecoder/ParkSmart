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
      },
      boxShadow: {
        sheet: "0 -8px 40px rgba(12, 26, 20, 0.12)",
        drawer: "-4px 0 32px rgba(12, 26, 20, 0.08)",
      },
    },
  },
  plugins: [],
};
