# Decoder — AI-Powered Code Analysis & Documentation Platform

Transform complex codebases into plain-English insights, visual maps, and professional-grade documentation in minutes.

## 🎯 Overview

**Decoder** is an intelligent code analysis platform that leverages AI (GPT-4o) to automatically understand, visualize, and document your codebase — without requiring weeks of manual review. Built for developers, engineering leads, and technical stakeholders who need to understand code complexity, measure technical debt, and generate professional documentation at scale.

### Core Value Propositions

- **Understand any codebase in minutes** — not months
- **Turn code into plain English** with one upload
- **Quantify technical debt** in dollar terms your leadership understands
- **Generate professional documentation** automatically
- **Visualize architecture** with interactive mind maps and relationship graphs
- **Manage multi-repository systems** with cross-repo analysis

---

## ✨ Key Features

### 🔍 AI-Powered Code Analysis
Decoder's AI engine analyzes your code and produces:

- **Architecture Analysis** — Identifies functions, classes, imports, and API endpoints
- **Business Intent Review** — Translates code into plain English any stakeholder can understand
- **Design Pattern Detection** — Recognizes MVC, Singleton, and other architectural patterns
- **Data Flow Mapping** — Traces how data moves through the system
- **Health Scoring** — Generates scores across Maintainability, Scalability, and Testability dimensions
- **Code Smell Detection** — Surfaces hidden issues and technical debt

### 📤 Multiple Import Options

- **ZIP File Upload** — Drop in any local project archive (up to 100MB)
- **GitHub Repository Import** — Connect to public or private repos via Personal Access Token

### 📊 Interactive Visualizations

- **Mind Map** — Zoomable, hierarchical view of project structure
- **Relationship Graph** — D3.js-powered node-edge diagram showing file, class, and function connections

### 💰 Technical Debt & ROI Calculator

- **Financial Translation** — Estimates the real cost of fixing technical debt by developer seniority (Junior, Mid, Senior)
- **Remediation Timeline** — Gantt-style visual timeline for fixing issues
- **Actionable Insights** — Break down debt by severity and impact

### 📝 Automated Documentation Generator

Generate professional documentation automatically:

- **Architecture Documentation** — System design and high-level overview
- **Security Analysis** — Identifies potential security concerns
- **File-Level Documentation** — Details for every component
- **Export Formats** — Microsoft Word (DOCX), Markdown, or HTML

### 🏗️ Multi-Repository Systems Analysis

For teams managing microservices or multiple repositories:

- Group multiple analyses into a **"System"** for cross-repo comparison
- Detect **duplicate functions** and **shared API surfaces**
- Identify dependencies and overlaps between services

### 🤖 AI Change Advisor

Before shipping code changes:

- Describe a proposed change in plain English
- Analyzer identifies what could break and affected components
- Get impact assessment before merge

### 👥 Team & Company Management

- **Multi-user support** with role-based access control
- **Subscription tiers** — Solo, Team, and Enterprise options
- **Trial period** — 7-day trial for new users
- **Shared analyses** — Share insights within your company
- **Company invitations** — Manage team membership

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask 3.1+
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Server**: Gunicorn
- **Authentication**: Flask-Login with JWT support
- **API Client**: OpenAI 

### Frontend
- **HTML/CSS/JavaScript** — Vanilla JS with D3.js for visualizations
- **Styling**: Custom CSS with support for multiple themes
- **Visualizations**: 
  - D3.js for relationship graphs
  - Custom mind map rendering
  - Interactive terminal-style UI components

### Development & Monitoring
- **Testing**: Playwright for end-to-end testing
- **Error Tracking**: Sentry
- **Document Generation**: python-docx
- **Async Tasks**: PlaywrightBrowser-based analysis

---

## 📋 Requirements

- Python 3.11+
- PostgreSQL 12+
- OpenAI API key 
- Modern web browser (Chrome, Firefox, Safari, Edge)

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Configure Environment Variables

Create a `.env` file or export the following:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/vibedecoder

# Session & Security
SESSION_SECRET=your-secret-key-here

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# GitHub Integration (optional)
GITHUB_API_TOKEN=your-github-token

# Sentry (optional)
SENTRY_DSN=your-sentry-dsn
```

### 3. Initialize Database

```bash
python
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

### 4. Run Development Server

```bash
python main.py
```

The application will start at `http://localhost:5000`

### 5. Production Deployment

```bash
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
```

---

## 📁 Project Structure

```
├── app.py                           # Flask app factory and configuration
├── main.py                          # Application entry point
├── models.py                        # SQLAlchemy database models
├── routes.py                        # Flask blueprints and API endpoints
├── auth.py                          # Authentication and authorization
├── 
├── ai_analyzer.py                   # Core AI analysis engine
├── change_advisor.py                # AI-powered change impact analysis
├── documentation_generator.py       # Automated docs generation
├── github_integration.py            # GitHub repo import integration
├── graph_processor.py               # Relationship graph generation
├── mindmap_processor.py             # Mind map data processing
├── system_analyzer.py               # Multi-repo systems analysis
├── api_analytics.py                 # Analytics and metrics
├── analysis_progress.py             # Real-time analysis progress tracking
├──
├── static/                          # Frontend assets
│   ├── css/                         # Stylesheets
│   │   ├── decoder.css
│   │   ├── graph.css
│   │   ├── mindmap.css
│   │   └── terminal.css
│   ├── js/                          # Client-side scripts
│   │   ├── app.js
│   │   ├── graph.js
│   │   ├── mindmap.js
│   │   └── chat.js
│   └── images/
│
├── templates/                       # Jinja2 HTML templates
│   ├── base.html                    # Base layout
│   ├── index.html                   # Home page
│   ├── login.html                   # Authentication
│   ├── register.html
│   ├── dashboard.html               # User dashboard
│   ├── upload.html                  # Code upload interface
│   ├── analysis.html                # Results dashboard
│   ├── documentation.html           # Generated docs viewer
│   ├── graph.html                   # Graph visualization
│   ├── team_admin.html              # Team management
│   ├── documentation_sections/      # Doc templates
│   └── systems/                     # Multi-repo system templates
│
├── pyproject.toml                   # Project metadata and dependencies
└── README.md                        # This file
```

---

## 🔑 Core Modules

### `ai_analyzer.py`
Handles the core AI analysis pipeline:
- Code parsing and understanding
- Health score calculation
- Design pattern detection
- Business intent translation
- Individual file and full codebase analysis

### `documentation_generator.py`
Automated documentation generation:
- Architecture documentation
- Security analysis documentation
- File-level documentation
- Export to DOCX, Markdown, or HTML formats

### `graph_processor.py`
Generates interactive relationship graphs:
- File and class dependency visualization
- Function call chains
- Data flow connections
- D3.js rendering data

### `mindmap_processor.py`
Creates hierarchical mind map representations:
- Project structure visualization
- Zoomable navigation
- Component categorization

### `github_integration.py`
GitHub repository integration:
- Clone and analyze public/private repos
- Personal Access Token authentication
- Recursive dependency analysis

### `change_advisor.py`
AI-powered change impact analysis:
- Proposes code changes in natural language
- Identifies affected components
- Predicts breaking changes
- Provides mitigation strategies

---

## 🗄️ Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts with authentication |
| `companies` | Organization/team accounts |
| `subscriptions` | Subscription tier and billing info |
| `analyses` | Code analysis results and metadata |
| `code_files` | Individual file analysis and metrics |
| `systems` | Multi-repository system groupings |
| `system_repos` | Repos within a system |
| `system_analysis` | Cross-repo analysis results |
| `change_requests` | Proposed code changes for analysis |

---

## 🔐 Authentication & Authorization

- **User Login** — Username/password with session management
- **JWT Support** — Token-based API access
- **Role-Based Access Control** — Admin, Company Admin, User roles
- **Company Isolation** — Users access only their company's data
- **Shared Analyses** — Control sharing within company scope

---

## 📊 Health Scoring System

Decoder generates health scores across three dimensions:

### Maintainability (0-100)
- Code organization and structure
- Documentation and clarity
- Naming conventions
- Test coverage

### Scalability (0-100)
- Architectural patterns
- Performance considerations
- Resource management
- System decomposition

### Testability (0-100)
- Test coverage
- Mock-friendly design
- Dependency injection
- Unit testing potential

---

## 🌐 API Endpoints

### Analysis
- `POST /upload` — Upload ZIP file for analysis
- `POST /import-repo` — Import GitHub repository
- `GET /analysis/<id>` — Retrieve analysis results
- `GET /analysis/<id>/health` — Get health scores
- `GET /analysis/<id>/graph` — Get relationship graph data
- `GET /analysis/<id>/mindmap` — Get mind map data

### Documentation
- `POST /analysis/<id>/generate-docs` — Generate documentation
- `GET /analysis/<id>/docs` — Download generated documentation
- `GET /analysis/<id>/docs/preview` — Preview documentation

### Systems
- `POST /systems` — Create multi-repo system
- `POST /systems/<id>/repos` — Add repo to system
- `GET /systems/<id>/analysis` — Get cross-repo analysis

### Change Advisory
- `POST /change-request` — Analyze proposed code change
- `GET /change-request/<id>/impact` — Get impact analysis

### Team Management
- `POST /company/invite` — Invite team member
- `GET /company/members` — List team members
- `POST /company/members/<id>/role` — Update member role

---

## 🧪 Testing

Run end-to-end tests with Playwright:

```bash
playwright test
```

---

## 📈 Performance Considerations

- **Pool Configuration** — PostgreSQL connection pooling configured for stability
- **Large File Support** — Handles projects up to 100MB
- **Streaming Analysis** — Real-time progress updates during analysis
- **Caching** — Health scores and visualizations cached efficiently
- **Async Processing** — Long-running analyses process asynchronously

---

## 🚨 Error Handling & Monitoring

- **Sentry Integration** — Automatic error tracking and reporting
- **Logging** — Comprehensive logging throughout the application
- **Graceful Degradation** — Continues operation with partial data when possible
- **User Feedback** — Clear error messages for user-facing issues

---

## 🔄 Configuration

Key configuration options in `app.py`:

```python
# Database connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_recycle": 120,
    "pool_pre_ping": True,
    "pool_size": 5,
    "max_overflow": 10,
}

# File upload limit
MAX_CONTENT_LENGTH = 110 * 1024 * 1024  # 110MB

```

## 📞 Support & Contact

For issues, feature requests, or questions:
- Raise an Issue on GitHub

---

## 🗺️ Roadmap

Potential future enhancements:
- [ ] Docker Container
- [ ] Real-time collaboration on analyses
- [ ] Custom AI model fine-tuning
- [ ] VS Code extension
- [ ] IDE integrations (JetBrains, Visual Studio)
- [ ] GraphQL API
- [ ] Advanced team workflows
- [ ] Mobile app for documentation browsing

---

## 🔍 Troubleshooting

### Database Connection Issues
Ensure PostgreSQL is running and `DATABASE_URL` is correct:
```bash
psql $DATABASE_URL -c "SELECT 1"
```

### OpenAI API Errors
Verify `OPENAI_API_KEY` is valid and has sufficient quota:
```bash
python -c "import openai; print(openai.OpenAI())"
```

### Session Secret Warning
In production, always set `SESSION_SECRET` environment variable to a secure random value.

### Large File Upload Timeout
Increase `MAX_CONTENT_LENGTH` in `app.py` and adjust web server timeouts accordingly.

---

**Built with ❤️ by the Decoder team**
