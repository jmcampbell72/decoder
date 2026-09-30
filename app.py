import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()


def create_app():

    app = Flask(__name__)

    app.secret_key = os.environ.get("SESSION_SECRET", "ENTER YOUR OWN SECRET")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "postgresql:")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 120,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "connect_args": {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 110 * 1024 * 1024  # 110MB to accommodate 100MB ZIP uploads

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    with app.app_context():
        from models import User, Analysis, CodeFile, Company, Subscription, CompanyInvite, System, SystemRepo, SystemAnalysis
        from sqlalchemy import text

        db.create_all()

        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_company_admin BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id)",
            "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS is_shared BOOLEAN NOT NULL DEFAULT FALSE",
            # Move subscription_status and trial_started_at from users to companies
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) NOT NULL DEFAULT 'trial'",
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMP DEFAULT NOW()",
            # Analytics: track last login time per user
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP",
            # Cross-repo HTTP call extraction for system analysis
            "ALTER TABLE code_files ADD COLUMN IF NOT EXISTS http_calls JSONB",
        ]
        for sql in migrations:
            try:
                db.session.execute(text(sql))
                db.session.commit()
            except Exception as migration_err:
                db.session.rollback()
                logging.warning(f"Migration skipped: {migration_err}")

        # One-off migration tracking table — used to gate data migrations that must run exactly once
        try:
            db.session.execute(text("CREATE TABLE IF NOT EXISTS _migration_log (migration_name VARCHAR PRIMARY KEY, applied_at TIMESTAMP DEFAULT NOW())"))
            db.session.commit()
        except Exception as ml_err:
            db.session.rollback()
            logging.warning(f"Migration log table creation skipped: {ml_err}")

        # One-off: clear stale system graph data so it regenerates with updated finding colours
        # (Duplicate changed from #f97316→#f59e0b, Common Pattern #a855f7→#06b6d4)
        try:
            already_done = db.session.execute(
                text("SELECT 1 FROM _migration_log WHERE migration_name = 'system_graph_colour_fix_2026'")
            ).first()
            if not already_done:
                db.session.execute(text("UPDATE system_analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("INSERT INTO _migration_log (migration_name) VALUES ('system_graph_colour_fix_2026')"))
                db.session.commit()
                logging.info("One-off: cleared stale system graph data for colour fix")
        except Exception as colour_err:
            db.session.rollback()
            logging.warning(f"System graph colour cache clear skipped: {colour_err}")

        # One-off: clear system graph cache so nodes regenerate with analysis_id in metadata
        try:
            already_done = db.session.execute(
                text("SELECT 1 FROM _migration_log WHERE migration_name = 'system_graph_analysis_id_metadata_2026'")
            ).first()
            if not already_done:
                db.session.execute(text("UPDATE system_analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("INSERT INTO _migration_log (migration_name) VALUES ('system_graph_analysis_id_metadata_2026')"))
                db.session.commit()
                logging.info("One-off: cleared stale system graph data for analysis_id metadata")
        except Exception as meta_err:
            db.session.rollback()
            logging.warning(f"System graph analysis_id metadata cache clear skipped: {meta_err}")

        # One-off: clear all graph_data caches so api_endpoint nodes regenerate with real
        # path labels (was falling back to "/" due to "endpoint" vs "path" key mismatch)
        try:
            already_done = db.session.execute(
                text("SELECT 1 FROM _migration_log WHERE migration_name = 'graph_api_label_fix_2026'")
            ).first()
            if not already_done:
                db.session.execute(text("UPDATE analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("UPDATE system_analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("INSERT INTO _migration_log (migration_name) VALUES ('graph_api_label_fix_2026')"))
                db.session.commit()
                logging.info("One-off: cleared stale graph_data for api_endpoint label fix")
        except Exception as api_label_err:
            db.session.rollback()
            logging.warning(f"Graph api label cache clear skipped: {api_label_err}")

        # One-off: clear system graph cache so cross-repo call edges regenerate
        try:
            already_done = db.session.execute(
                text("SELECT 1 FROM _migration_log WHERE migration_name = 'system_graph_cross_repo_edges_2026'")
            ).first()
            if not already_done:
                db.session.execute(text("UPDATE system_analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("INSERT INTO _migration_log (migration_name) VALUES ('system_graph_cross_repo_edges_2026')"))
                db.session.commit()
                logging.info("One-off: cleared stale system graph data for cross-repo call edges")
        except Exception as cross_edge_err:
            db.session.rollback()
            logging.warning(f"System graph cross-repo edge cache clear skipped: {cross_edge_err}")

        # One-off: re-clear system graph cache after adding method-aware edge matching
        try:
            already_done = db.session.execute(
                text("SELECT 1 FROM _migration_log WHERE migration_name = 'system_graph_method_aware_edges_2026'")
            ).first()
            if not already_done:
                db.session.execute(text("UPDATE system_analyses SET graph_data = NULL WHERE graph_data IS NOT NULL"))
                db.session.execute(text("INSERT INTO _migration_log (migration_name) VALUES ('system_graph_method_aware_edges_2026')"))
                db.session.commit()
                logging.info("One-off: cleared stale system graph data for method-aware cross-repo edge matching")
        except Exception as method_edge_err:
            db.session.rollback()
            logging.warning(f"System graph method-aware edge cache clear skipped: {method_edge_err}")

        # Drop obsolete columns from users (wix_member_id, subscription_status, trial_started_at)
        drop_migrations = [
            "ALTER TABLE users DROP COLUMN IF EXISTS wix_member_id",
            "ALTER TABLE users DROP COLUMN IF EXISTS subscription_status",
            "ALTER TABLE users DROP COLUMN IF EXISTS trial_started_at",
        ]
        for sql in drop_migrations:
            try:
                db.session.execute(text(sql))
                db.session.commit()
            except Exception as drop_err:
                db.session.rollback()
                logging.warning(f"Drop migration skipped: {drop_err}")

        if not User.query.filter_by(email='admin@vibedecoder.com').first():
            from werkzeug.security import generate_password_hash
            from datetime import datetime

            company = Company()
            company.name = "Admin Workspace"
            company.subscription_status = 'active'
            db.session.add(company)
            db.session.flush()

            subscription = Subscription()
            subscription.company_id = company.id
            subscription.tier = 'enterprise'
            db.session.add(subscription)

            admin_user = User()
            admin_user.username = 'admin'
            admin_user.email = 'admin@vibedecoder.com'
            admin_user.password_hash = generate_password_hash('admin123')
            admin_user.role = 'admin'
            admin_user.company_id = company.id
            admin_user.is_company_admin = True
            db.session.add(admin_user)
            db.session.commit()
            logging.info("Created default admin user: admin@vibedecoder.com / admin123")

    from routes import main_bp
    from auth import auth_bp
    from team import team_bp
    from api_analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(team_bp, url_prefix='/team')
    app.register_blueprint(analytics_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_wix_urls():
        return {
            'wix_pricing_url': app.config['WIX_PRICING_URL'],
            'wix_portal_url': app.config['WIX_PORTAL_URL'],
        }

    @app.context_processor
    def inject_team_access():
        """Inject team access flag using a direct query to avoid lazy-loading issues."""
        from flask_login import current_user
        team_access = False
        if current_user.is_authenticated and current_user.company_id:
            from models import Subscription
            sub = Subscription.query.filter_by(company_id=current_user.company_id).first()
            team_access = sub is not None and sub.allows_team()
        return {'team_access': team_access}

    @app.context_processor
    def inject_brand():
        from flask import request, session

        host_brand_map = {
            "decoder.junkshon.com": "junkshon",
            "app.decoderco.com": "decoder",
        }
        host = request.host.split(":")[0].lower()
        if host in host_brand_map:
            brand = host_brand_map[host]
        else:
            brand_param = request.args.get("brand", "").lower()
            if brand_param in ["junkshon", "decoder", "fastfood", "terminal"]:
                session["brand"] = brand_param
                brand = brand_param
            elif "brand" in session and session["brand"] in ["junkshon", "decoder", "fastfood", "terminal"]:
                brand = session["brand"]
            else:
                brand = os.environ.get("APP_BRAND", "junkshon").lower()

        brand_config = {
            "junkshon": {
                "name": "DeCoder",
                "company": "Junkshon",
                "website": "www.junkshon.com",
                "logo": "images/logo.png",
                "css": "css/custom.css",
                "favicon": "images/favicon_junkshon.ico",
                "footer_text": "DeCoder - Junkshon 2026 | www.junkshon.com",
                "dashboard_front": "images/dashboard-front.png",
                "dashboard_back": "images/dashboard-back.png"
            },
            "decoder": {
                "name": "Decoder",
                "company": "Decoder",
                "website": "decoder.app",
                "logo": "images/logo_decoder.png",
                "css": "css/decoder.css",
                "footer_text": "Decoder 2026",
                "dashboard_front": "images/decoder-front.png",
                "dashboard_back": "images/decoder-back.png"
            },
            "fastfood": {
                "name": "DEcoder Combo",
                "company": "The Code Kitchen",
                "website": "www.junkshon.com",
                "logo": "images/logo_fastfood.svg",
                "css": "css/fastfood.css",
                "footer_text": "DEcoder Combo — Served fresh by The Code Kitchen, 2026 🍔 No code was harmed in the making of this analysis.",
                "dashboard_front": "images/dashboard-front.png",
                "dashboard_back": "images/dashboard-back.png"
            },
            "terminal": {
                "name": "DeCoder",
                "company": "Junkshon",
                "website": "www.junkshon.com",
                "logo": "images/logo_terminal.svg",
                "css": "css/terminal.css",
                "footer_text": "[ DeCoder Terminal v2026 ] -- (C) Junkshon -- www.junkshon.com",
                "dashboard_front": "images/dashboard-front.png",
                "dashboard_back": "images/dashboard-back.png"
            }
        }
        return {
            "brand": brand_config.get(brand, brand_config["junkshon"]),
            "brand_name": brand
        }

    return app


app = create_app()
