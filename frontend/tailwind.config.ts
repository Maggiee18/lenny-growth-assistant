import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f2f6fc",
          100: "#e3ecf9",
          200: "#c2d6f0",
          300: "#8fb3e2",
          400: "#5689cd",
          500: "#3468b3",
          600: "#265193",
          700: "#204178",
          800: "#1e3763",
          900: "#1c3054",
        },
      },
    },
  },
  plugins: [],
};

export default config;
