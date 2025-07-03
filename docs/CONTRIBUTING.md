# Contributing to Build Canada Outcome Tracker

Thank you for your interest in contributing to the Build Canada Outcome Tracker! This project aims to bring transparency to government promises and their progress. We welcome contributions from developers, policy analysts, and citizens who share our vision.

## 🤝 Ways to Contribute

### 1. Code Contributions
- Fix bugs and implement features
- Improve performance and accessibility
- Add tests and documentation
- Refactor for better maintainability

### 2. Data & Research
- Verify promise tracking accuracy
- Research and add new evidence
- Identify missing promises
- Fact-check existing data

### 3. Design & UX
- Improve UI/UX design
- Create better data visualizations
- Enhance mobile experience
- Improve accessibility

### 4. Documentation
- Fix typos and clarify explanations
- Add examples and tutorials
- Translate documentation
- Create user guides

## 🚀 Getting Started

### 1. Join the Community
Fill out our [volunteer intake form](https://5nneq7.share-na3.hsforms.com/2l9iIH2gFSomphjDe-ci5OQ) to get connected with the team.

### 2. Set Up Development Environment
```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/OutcomeTracker.git
cd OutcomeTracker

# Install dependencies
pnpm install

# Create a branch for your work
git checkout -b feature/your-feature-name

# Start development server
pnpm turbo
```

### 3. Find an Issue
- Check [open issues](https://github.com/BuildCanada/OutcomeTracker/issues)
- Look for `good first issue` labels
- Ask in discussions if you need guidance

## 📋 Development Process

### 1. Before You Start
- Check if an issue already exists
- Comment on the issue to claim it
- Discuss major changes before implementing

### 2. Making Changes

#### Code Style
Follow the existing patterns in the codebase:
```typescript
// ✅ Good: Clear, typed, documented
interface PromiseUpdate {
  id: number;
  progress: number;
  evidence?: Evidence;
}

export function updatePromiseProgress(
  update: PromiseUpdate
): Promise<void> {
  // Implementation with error handling
}

// ❌ Bad: Unclear, untyped
function update(data: any) {
  // Magic happens here
}
```

#### Component Guidelines
```typescript
// Follow consistent component structure
interface ComponentProps {
  // Required props first
  id: string;
  title: string;
  
  // Optional props with defaults
  variant?: 'primary' | 'secondary';
  className?: string;
}

export function Component({ 
  id,
  title,
  variant = 'primary',
  className 
}: ComponentProps) {
  // Hooks at the top
  const [state, setState] = useState(false);
  
  // Early returns for edge cases
  if (!id) return null;
  
  // Main render
  return (
    <div className={cn('base-styles', className)}>
      {/* Content */}
    </div>
  );
}
```

### 3. Testing Your Changes

#### Run Tests
```bash
# Type checking
pnpm tsc --noEmit

# Linting
pnpm lint

# Unit tests (when available)
pnpm test

# Build test
pnpm build
```

#### Manual Testing Checklist
- [ ] Feature works as expected
- [ ] No console errors
- [ ] Responsive on mobile
- [ ] Keyboard accessible
- [ ] Cross-browser compatible

### 4. Committing Changes

#### Commit Message Format
Follow conventional commits:
```bash
# Format: <type>(<scope>): <subject>

feat(charts): add GDP per capita visualization
fix(api): resolve promise loading timeout
docs(readme): update deployment instructions
style(ui): improve mobile navigation spacing
refactor(hooks): simplify data fetching logic
test(promises): add unit tests for progress calculation
chore(deps): update Chart.js to v4.4.0
```

#### Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests
- `chore`: Changes to build process or auxiliary tools

### 5. Submitting a Pull Request

#### PR Checklist
- [ ] Descriptive title following commit format
- [ ] Clear description of changes
- [ ] Screenshots for UI changes
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No merge conflicts

#### PR Template
```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Local testing completed
- [ ] Added/updated tests
- [ ] Cross-browser tested

## Screenshots (if applicable)
[Add screenshots here]

## Related Issues
Fixes #123
```

## 🏗️ Project Structure

Understanding the codebase:
```
app/                # Next.js pages and layouts
├── [department]/   # Dynamic department routes
components/         # Reusable React components
├── charts/        # Chart visualizations
├── ui/            # Base UI components
lib/               # Utilities and types
metrics/           # Static data files
docs/              # Documentation
```

## 📊 Working with Data

### Adding New Metrics
1. Add data file to `/metrics/[source]/`
2. Create chart component in `/components/charts/`
3. Update `DepartmentMetrics` component
4. Add documentation

### Updating Promise Data
Promise data comes from the API. To suggest changes:
1. Create an issue with evidence
2. Include sources and rationale
3. Tag as `data-update`

## 🐛 Reporting Issues

### Bug Reports
Include:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Screenshots/console errors
- Browser and OS info

### Feature Requests
Include:
- Problem it solves
- Proposed solution
- Alternative considered
- Mock-ups (if applicable)

## 🔒 Security

### Reporting Security Issues
Do NOT create public issues for security vulnerabilities.
Email: security@buildcanada.com

### Security Best Practices
- Never commit secrets or API keys
- Validate all user inputs
- Use environment variables
- Follow OWASP guidelines

## 📝 Code Review Process

### What We Look For
1. **Functionality**: Does it work as intended?
2. **Code Quality**: Is it clean and maintainable?
3. **Performance**: No unnecessary re-renders or API calls?
4. **Security**: No vulnerabilities introduced?
5. **Tests**: Are changes tested?
6. **Documentation**: Is it documented?

### Review Timeline
- Initial review: 2-3 business days
- Follow-up reviews: 1-2 business days
- Be patient - we're volunteers!

## 🎯 Coding Standards

### TypeScript
- Strict mode enabled
- No `any` types without justification
- Interfaces over type aliases
- Descriptive variable names

### React
- Functional components only
- Hooks for state management
- Memoize expensive operations
- Error boundaries for robustness

### Styling
- Tailwind CSS utilities
- Mobile-first approach
- Consistent spacing scale
- Accessible color contrasts

## 🤖 Automation

### GitHub Actions
Our CI/CD pipeline runs:
- Type checking
- Linting
- Build verification
- Deployment (on merge)

### Pre-commit Hooks
Set up locally:
```bash
pnpm add -D husky lint-staged
npx husky install
```

## 📚 Resources

### Documentation
- [Architecture Overview](./ARCHITECTURE.md)
- [Development Guide](./DEVELOPMENT.md)
- [API Integration](./API_INTEGRATION.md)
- [Component Guide](./COMPONENTS.md)

### External Resources
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [Tailwind CSS](https://tailwindcss.com/docs)

## 🙏 Recognition

Contributors are recognized in:
- GitHub contributors page
- Annual community reports
- Build Canada volunteer highlights

## ❓ Questions?

- Check existing [discussions](https://github.com/BuildCanada/OutcomeTracker/discussions)
- Join our community chat
- Email: dev@buildcanada.com

---

Thank you for helping build a more transparent democracy! 🇨🇦 