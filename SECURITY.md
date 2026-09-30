# Security Policy

## Reporting a Vulnerability

**Please DO NOT create a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability, please report it responsibly by emailing the maintainers.

### How to Report

Send an email with the following information:

**To**: [Maintainer Email] or create a private security advisory on GitHub

**Include**:
1. **Description** of the vulnerability
2. **Steps to reproduce** (if applicable)
3. **Potential impact** (what could an attacker do?)
4. **Suggested fix** (if you have one)
5. **Your contact information** (for follow-up)

### What to Expect

- **Acknowledgment**: We will confirm receipt within 48 hours
- **Updates**: We'll provide status updates every 3-5 days
- **Timeline**: We aim to release a fix within 14 days for critical issues
- **Credit**: We will credit you in the security advisory (unless you prefer anonymity)

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 0.1.x   | ✅ Yes             |
| < 0.1   | ❌ No              |

We recommend always running the latest version for security updates.

## Security Best Practices

### For Users

1. **Never commit `.env` files**
   ```bash
   # .env should never be in version control
   # Always use .env.example as a template
   ```

2. **Keep dependencies updated**
   ```bash
   pip install --upgrade pip
   pip install -e . --upgrade
   ```

3. **Use strong SESSION_SECRET**
   ```bash
   # Generate a secure secret
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. **Secure your database**
   - Use strong passwords
   - Run PostgreSQL on non-public network
   - Use SSL/TLS for database connections

5. **Monitor for security updates**
   - Watch the repository for releases
   - Check release notes for security patches
   - Update promptly when patches are released

### For Contributors

1. **Code Security**
   - Never hardcode secrets, API keys, or credentials
   - Use environment variables for all sensitive data
   - Review code for injection vulnerabilities (SQL, command, etc.)
   - Validate and sanitize user input

2. **Dependency Security**
   - Review dependencies before adding
   - Use versions with security fixes
   - Avoid unmaintained or suspicious packages
   - Report vulnerable dependencies

3. **Testing**
   - Test security-related changes thoroughly
   - Consider edge cases and malicious input
   - Look for common vulnerabilities (OWASP Top 10)

4. **Documentation**
   - Document security considerations
   - Explain authentication/authorization flow
   - Highlight security-sensitive code sections
   - Update security documentation with changes

## Known Security Measures

### Authentication
- User passwords hashed with werkzeug.security
- Session-based authentication with Flask-Login
- JWT support for API access
- Company-level access control

### Data Protection
- Database credentials via environment variables
- Secrets never logged or exposed in errors
- HTTPS recommended for production
- SQL injection protection via SQLAlchemy ORM

### Code Analysis
- AI analysis doesn't store user data
- Analysis results kept private
- Company access controls on shared analyses
- Audit trail for data access

## Vulnerability Disclosure Timeline

We follow responsible disclosure practices:

1. **Day 0**: Vulnerability reported and confirmed
2. **Day 1-3**: Initial assessment and reproduction
3. **Day 4-10**: Fix development and testing
4. **Day 11-14**: Security update released
5. **Day 15**: Public disclosure (after users have time to update)

Critical vulnerabilities may be expedited.

## Third-Party Security

### Dependencies
- Regular security updates for Python packages
- Monitoring for known vulnerabilities
- Consider using tools like:
  - `pip-audit` — Check for known vulnerabilities
  - `safety` — Check Python dependencies
  - Dependabot (GitHub) — Automated updates

### OpenAI Integration
- API keys never logged or stored
- Requests validated before sending
- Rate limiting to prevent abuse
- Error handling doesn't expose sensitive data

### GitHub Integration
- Personal access tokens via environment variables
- Tokens not logged or displayed
- Minimal required scopes requested
- Token rotation recommended

## Incident Response

If a security incident occurs:

1. **Severity Assessment**: Determine impact and urgency
2. **Notification**: Alert affected users and systems
3. **Remediation**: Develop and test fix
4. **Release**: Deploy security patch
5. **Post-Mortem**: Review and prevent recurrence

## Security Resources

### Learn More
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) — Common web vulnerabilities
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/) — Most dangerous software weaknesses
- [Python Security](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Flask Security](https://flask.palletsprojects.com/en/latest/security/)

### Tools
- `bandit` — Find common security issues in Python code
- `pip-audit` — Check Python packages for known vulnerabilities
- `safety` — Safety database of insecure dependencies
- `semgrep` — Custom security scanning rules

## Contact

- **Security Email**: [Add your contact]
- **GitHub Issues**: For non-security bugs only
- **Pull Requests**: For bug fixes and improvements

## Acknowledgments

We appreciate the security research community and responsible disclosure. Your efforts help keep open-source software secure for everyone.

---

**Last Updated**: 2026-09-30
