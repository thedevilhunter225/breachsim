import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#131722",
        mist: "#f4efe7",
        ember: "#da5a2a",
        moss: "#6b7d3c",
        tide: "#0f6877",
        slate: "#5f6777"
      },
      boxShadow: {
        card: "0 18px 50px rgba(19, 23, 34, 0.08)"
      },
      borderRadius: {
        xl2: "1.75rem"
      }
    }
  },
  plugins: []
};

export default config;
