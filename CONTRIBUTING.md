# Contributing to DeCoder

Thank you for your interest in contributing to DeCoder! We welcome contributions of all kinds, from bug reports and feature requests to code improvements and documentation.

## Getting Started

### Prerequisites
- Python 3.11 or higher
- PostgreSQL 12 or higher
- Git
- Virtual environment tool (venv or conda)

### Setting Up Your Development Environment

1. **Fork the repository**
   ```bash
   # Click "Fork" on GitHub
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR-USERNAME/decoder.git
   cd decoder
   ```

3. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -e .
   ```

5. **Copy the environment template**
   ```bash
   cp .env.example .env
   ```

6. **Configure your .env file**
   ```bash
   # Edit .env with your configuration
   # At minimum, you'll need:
   # - DATABASE_URL (PostgreSQL connection string)
   # - SESSION_SECRET (generate with: python -c "import secrets; print(secrets.token_hex(32))")
   # - OPENAI_API_KEY (for code analysis)
   ```

7. **Set up the database**
   ```bash
   python
   >>> from app import create_app, db
   >>> app = create_app()
   >>> with app.app_context():
   ...     db.create_all()
   >>> exit()
   ```

8. **Run the development server**
   ```bash
   python main.py
   # App will be available at http://localhost:5000
   ```

## Making Changes

### Creating a Feature Branch

1. **Create a descriptive branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or for bug fixes:
   git checkout -b fix/bug-description
   ```

2. **Make your changes**
   - Write clean, readable code
   - Add docstrings to functions and classes
   - Follow PEP 8 style guidelines
   - Comment complex logic

3. **Test your changes**
   ```bash
   # Run the app and test manually
   python main.py
   
   # Check for any obvious issues
   python -m py_compile ai_analyzer.py  # Example: check syntax
   ```

4. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: clear description of what was added"
   # Good: "Add code smell detection for duplicate functions"
   # Bad: "Fix stuff"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Open a Pull Request**
   - Go to GitHub and click "New Pull Request"
   - Provide a clear title and description
   - Link any related issues (e.g., "Fixes #123")
   - Explain what you changed and why

## Code Standards

### Style Guide
- Follow PEP 8 (Python Enhancement Proposal 8)
- Use 4 spaces for indentation
- Maximum line length: 120 characters
- Use descriptive variable and function names

### Documentation
- Add docstrings to all functions and classes:
  ```python
  def analyze_code(file_path: str) -> dict:
      """
      Analyze a code file and return insights.
      
      Args:
          file_path: Path to the code file to analyze
          
      Returns:
          Dictionary containing analysis results
          
      Raises:
          FileNotFoundError: If the file doesn't exist
      """
  ```

### Commit Messages
- Use imperative mood: "Add feature" not "Added feature"
- First line should be 50 characters or less
- Reference issues and pull requests liberally after the first line
- Separate subject from body with a blank line

Example:
```
Add AI-powered code smell detection

- Implement pattern recognition for common code smells
- Add configuration for detection sensitivity
- Include remediation suggestions in results

Fixes #42
```

## Reporting Issues

### Bug Reports
Please include:
- **Clear description** of the bug
- **Steps to reproduce** the issue
- **Expected behavior** vs **actual behavior**
- **Environment details**: OS, Python version, PostgreSQL version
- **Error messages** or logs
- **Screenshots** if applicable

### Feature Requests
Please include:
- **Clear description** of the desired feature
- **Use case** and **motivation**
- **Possible implementation** approach (if you have ideas)
- **Examples** of similar features in other tools

## Development Tips

### Useful Commands
```bash
# Run the development server
python main.py

# Check Python syntax
python -m py_compile filename.py

# Generate a new SESSION_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# Access the database
psql $DATABASE_URL
```

### Project Structure
- `app.py` — Flask app initialization
- `main.py` — Entry point
- `models.py` — Database models
- `routes.py` — API endpoints
- `ai_analyzer.py` — Core AI analysis engine
- `templates/` — HTML templates
- `static/` — CSS, JavaScript, images
- `tests/` — Test files (when added)

### Common Issues

**Import Errors**
```bash
# Reinstall the package in development mode
pip install -e .
```

**Database Connection Issues**
```bash
# Verify PostgreSQL is running and connection string is correct
psql $DATABASE_URL -c "SELECT 1"
```

**Missing Environment Variables**
```bash
# Check your .env file has all required variables
cat .env
```

## Pull Request Process

1. **Update** your fork from main branch
2. **Write tests** for new functionality (if applicable)
3. **Update documentation** if changing behavior
4. **Follow code standards** (style, docstrings, comments)
5. **Provide clear PR description** with motivation and changes
6. **Link related issues** in the PR description
7. **Be responsive** to feedback and requests for changes

## Review Process

- At least one maintainer will review your PR
- Changes may be requested before merging
- Once approved, your PR will be merged into main
- Your contribution will be credited in release notes

## Licensing

By contributing to DeCoder, you agree that your contributions will be licensed under the MIT License. This ensures the project remains open-source and free for everyone to use.

## Questions?

- **Open an issue** for questions about contributing
- **Check existing issues** for similar questions
- **Review the README** for project overview
- **Read SECURITY.md** for security guidelines

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions. We're committed to providing a welcoming and harassment-free experience for everyone.

---

Thank you for contributing to DeCoder! 🎉
