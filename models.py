import uuid
from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from sqlalchemy import Text, JSON


class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_status = db.Column(db.String(20), default='trial', nullable=False)
    trial_started_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscription = db.relationship('Subscription', backref='company', uselist=False, cascade='all, delete-orphan')
    members = db.relationship('User', backref='company', lazy=True)
    invites = db.relationship('CompanyInvite', backref='company', lazy=True, cascade='all, delete-orphan')
    analyses = db.relationship('Analysis', backref='company', lazy=True)

    def __repr__(self):
        return f'<Company {self.name}>'

    def get_member_count(self):
        return User.query.filter_by(company_id=self.id).count()

    def get_trial_days_remaining(self):
        if self.subscription_status != 'trial' or not self.trial_started_at:
            return 0
        trial_end = self.trial_started_at + timedelta(days=7)
        remaining = trial_end - datetime.utcnow()
        return max(0, remaining.days)

    def is_trial_expired(self):
        if self.subscription_status != 'trial':
            return False
        return self.get_trial_days_remaining() == 0

    def can_access_system(self):
        if self.subscription_status == 'cancelled':
            return False
        if self.subscription_status == 'trial' and self.is_trial_expired():
            return False
        return True

    def get_status_display(self):
        status_map = {
            'active': 'Active',
            'trial': 'Trial',
            'partner': 'Partner',
            'cancelled': 'Cancelled',
        }
        return status_map.get(self.subscription_status, 'Unknown')

    def get_status_badge_class(self):
        badge_map = {
            'active': 'success',
            'trial': 'warning',
            'partner': 'primary',
            'cancelled': 'danger',
        }
        return badge_map.get(self.subscription_status, 'secondary')


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False, unique=True)
    tier = db.Column(db.String(20), nullable=False, default='solo')  # 'solo', 'team', 'enterprise'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Subscription {self.tier} for company {self.company_id}>'

    def max_seats(self):
        if self.tier == 'solo':
            return 1
        elif self.tier == 'team':
            return 5
        else:
            return None

    def can_add_user(self, current_member_count):
        limit = self.max_seats()
        if limit is None:
            return True
        return current_member_count < limit

    def get_tier_display(self):
        return self.tier.capitalize()

    def get_tier_badge_class(self):
        badge_map = {
            'solo': 'secondary',
            'team': 'primary',
            'enterprise': 'warning',
        }
        return badge_map.get(self.tier, 'secondary')

    def allows_team(self):
        return self.tier in ('team', 'enterprise')


class CompanyInvite(db.Model):
    __tablename__ = 'company_invites'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    invited_email = db.Column(db.String(120), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='invites_sent')
    used_by = db.relationship('User', foreign_keys=[used_by_id], backref='invite_used')

    def __repr__(self):
        return f'<CompanyInvite {self.token[:8]}... company={self.company_id}>'

    def is_used(self):
        return self.used_at is not None

    @staticmethod
    def generate_token():
        return uuid.uuid4().hex


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='reviewer', nullable=False)  # 'admin' or 'reviewer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    last_login = db.Column(db.DateTime, nullable=True)
    hide_onboarding = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    is_company_admin = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def is_admin(self):
        return self.role == 'admin'

    def is_reviewer(self):
        return self.role in ['admin', 'reviewer']

    def can_access_system(self):
        """Delegates to company-level access check."""
        if self.company_id and self.company:
            return self.company.can_access_system()
        return True

    def get_company_subscription(self):
        if self.company_id and self.company:
            return self.company.subscription
        return None

    def has_team_access(self):
        sub = self.get_company_subscription()
        return sub is not None and sub.allows_team()


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(Text)
    source_type = db.Column(db.String(20), nullable=False)  # 'upload' or 'github'
    source_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')  # 'pending', 'analyzing', 'completed', 'failed'
    analysis_results = db.Column(JSON)
    diagram_data = db.Column(JSON)
    mindmap_data = db.Column(JSON)
    graph_data = db.Column(JSON)
    ai_insights = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    is_shared = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    code_files = db.relationship('CodeFile', backref='analysis', lazy=True, cascade='all, delete-orphan')
    events = db.relationship('AnalysisEvent', backref='analysis', lazy=True, cascade='all, delete-orphan', order_by='AnalysisEvent.order_index')

    def __repr__(self):
        return f'<Analysis {self.name}>'


class CodeFile(db.Model):
    __tablename__ = 'code_files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    language = db.Column(db.String(50), nullable=False)
    content = db.Column(Text, nullable=False)
    size_bytes = db.Column(db.Integer)
    line_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    functions = db.Column(JSON)
    classes = db.Column(JSON)
    imports = db.Column(JSON)
    apis = db.Column(JSON)
    http_calls = db.Column(JSON)
    quality_metrics = db.Column(JSON)

    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)

    def __repr__(self):
        return f'<CodeFile {self.filename}>'

    @property
    def extension(self):
        return self.filename.split('.')[-1].lower() if '.' in self.filename else ''


class ChangeRequest(db.Model):
    __tablename__ = 'change_requests'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    description = db.Column(Text, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    result = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    analysis = db.relationship('Analysis', backref='change_requests')
    user = db.relationship('User', backref='change_requests')

    def __repr__(self):
        return f'<ChangeRequest {self.id} - {self.status}>'
class System(db.Model):
    __tablename__ = 'systems'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)

    repos = db.relationship('SystemRepo', backref='system', lazy=True, cascade='all, delete-orphan')
    analyses = db.relationship('SystemAnalysis', backref='system', lazy=True, cascade='all, delete-orphan',
                               order_by='SystemAnalysis.created_at.desc()')

    def __repr__(self):
        return f'<System {self.name}>'

    @property
    def latest_analysis(self):
        return self.analyses[0] if self.analyses else None

    @property
    def linked_analyses(self):
        return [sr.analysis for sr in self.repos if sr.analysis is not None]


class SystemRepo(db.Model):
    __tablename__ = 'system_repos'

    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey('systems.id'), nullable=False)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    analysis = db.relationship('Analysis', backref='system_repos', lazy='joined')

    def __repr__(self):
        return f'<SystemRepo system={self.system_id} analysis={self.analysis_id}>'


class SystemAnalysis(db.Model):
    __tablename__ = 'system_analyses'

    id = db.Column(db.Integer, primary_key=True)
    system_id = db.Column(db.Integer, db.ForeignKey('systems.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    duplicate_functions = db.Column(JSON)
    duplicate_services = db.Column(JSON)
    common_patterns = db.Column(JSON)
    cross_repo_apis = db.Column(JSON)
    aggregated_smells = db.Column(JSON)
    graph_data = db.Column(JSON)
    summary = db.Column(JSON)

    def __repr__(self):
        return f'<SystemAnalysis system={self.system_id} status={self.status}>'


class AnalysisEvent(db.Model):
    __tablename__ = 'analysis_events'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    stage = db.Column(db.String(50), nullable=False)
    stage_label = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    progress_percentage = db.Column(db.Integer, default=0)
    message = db.Column(db.String(500))
    order_index = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<AnalysisEvent {self.stage} - {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'stage': self.stage,
            'stage_label': self.stage_label,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress_percentage': self.progress_percentage,
            'message': self.message,
            'order_index': self.order_index
        }
