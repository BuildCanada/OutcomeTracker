const { FlatCompat } = require("@eslint/eslintrc");
const js = require("@eslint/js");
const nextPlugin = require("@next/eslint-plugin-next");
const tsPlugin = require("@typescript-eslint/eslint-plugin");
const tsParser = require("@typescript-eslint/parser");

const compat = new FlatCompat();

module.exports = [
  js.configs.recommended,
  ...compat.extends("next/core-web-vitals", "next/typescript", "prettier"),
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "@next/next": nextPlugin,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": "error",
      "prefer-const": "error",
      "no-var": "error",
      "@typescript-eslint/no-explicit-any": "error",
      // Disallow console.log but allow warn and error
      "no-console": ["error", { allow: ["warn", "error"] }],
      // Override all other rules to warnings temporarily
      "@typescript-eslint/ban-ts-comment": "warn",
      "@next/next/no-img-element": "warn",
      "@next/next/no-html-link-for-pages": "warn",
    },
  },
  // Override for chart files to disable no-explicit-any rule (excluding utils)
  // "any" types are often necessary for Chart.js compatibility
  {
    files: ["**/charts/**/*.{js,jsx,ts,tsx}"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
    // Exclude utils directory from this override
    ignores: ["**/charts/utils/**/*.{js,jsx,ts,tsx}"],
  },
];
