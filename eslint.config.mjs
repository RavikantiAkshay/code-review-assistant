import js from "@eslint/js";
import globals from "globals";
import pluginReact from "eslint-plugin-react";
import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    files: ["**/*.{js,mjs,cjs,jsx}"],
    plugins: { js },
    extends: ["js/recommended"],
    languageOptions: { globals: globals.browser },
    rules: {
      "semi": ["error", "always"],           // require semicolons
      "no-var": "error",                     // disallow var
      "comma-spacing": ["error", { "before": false, "after": true }],  // fix spacing around commas
      "no-unused-vars": "warn",
      "no-undef": "error"
    }
  },
  pluginReact.configs.flat.recommended,
]);
