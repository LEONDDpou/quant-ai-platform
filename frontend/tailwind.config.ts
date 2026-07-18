import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        gray: {
          750: '#2d3748',
          950: '#0b0f19',
        },
        blue: {
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          900: '#1e3a5f',
        },
        green: {
          300: '#86efac',
          400: '#4ade80',
          900: '#14532d',
        },
        red: {
          300: '#fca5a5',
          400: '#f87171',
          900: '#7f1d1d',
        },
        yellow: {
          300: '#fde047',
          400: '#facc15',
          900: '#713f12',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
export default config;
