module.exports = {
  "pre-commit": "pnpm run lint || (echo \"❌ Linting failed! Please fix the lint errors above and try committing again.\" && exit 1)",
};
