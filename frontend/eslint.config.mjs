import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    rules: {
      // The application does not enable React Compiler. These compiler-oriented rules
      // reject established data-loading effects without improving runtime correctness.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/exhaustive-deps": "off",
      // API payloads intentionally contain provider-specific JSON extensions.
      "@typescript-eslint/no-explicit-any": "off",
      // QR images are generated data URLs and cannot use Next's image optimizer.
      "@next/next/no-img-element": "off",
    },
  },
  globalIgnores([".next/**", "coverage/**", "next-env.d.ts"]),
]);
