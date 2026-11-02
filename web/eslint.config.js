import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.js", "tests/**/*.js"],
    languageOptions: { ecmaVersion: 2023, sourceType: "module", globals: { ...globals.browser } },
    rules: { "no-unused-vars": ["error", { argsIgnorePattern: "^_" }] },
  },
  { files: ["vite.config.js", "eslint.config.js"], languageOptions: { globals: { ...globals.node } } },
];
