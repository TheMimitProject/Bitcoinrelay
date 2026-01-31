# Contributing to Bitcoin Relay

Thank you for your interest in contributing to Bitcoin Relay! This document provides guidelines and information for contributors.

## Code of Conduct

Please be respectful and constructive in all interactions. We're all here to build something useful together.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** - Someone may have already reported the bug
2. **Create a detailed issue** including:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, etc.)
   - Any relevant logs or error messages

### Suggesting Features

1. **Open an issue** with the "feature request" label
2. Describe the feature and its use case
3. Explain why it would be valuable

### Submitting Code

1. **Fork the repository**
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Write/update tests** if applicable
5. **Run tests** to ensure nothing is broken:
   ```bash
   pytest tests/
   ```
6. **Commit with clear messages**:
   ```bash
   git commit -m "Add feature: brief description"
   ```
7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Open a Pull Request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/bitcoin-relay.git
cd bitcoin-relay

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest black flake8

# Run the app
python -m src.app
```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and reasonably sized
- Comment complex logic

You can format code with:
```bash
black src/
```

And check for issues with:
```bash
flake8 src/
```

## Testing

- Write tests for new functionality
- Ensure existing tests pass before submitting
- Test on both testnet and mainnet (with small amounts)

Run tests with:
```bash
pytest tests/ -v
```

## Security Considerations

Since this project handles Bitcoin private keys:

- **Never log private keys** or sensitive data
- **Always use encryption** for key storage
- **Be careful with error messages** - don't leak sensitive info
- **Test thoroughly** on testnet before mainnet
- Report security issues privately to maintainers

## Pull Request Guidelines

- Keep PRs focused on a single feature/fix
- Update documentation if needed
- Add tests for new functionality
- Ensure CI passes
- Be responsive to feedback

## Questions?

Open an issue with the "question" label if you need help or clarification.

Thank you for contributing! 🙏
