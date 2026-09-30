import os
import logging
from datetime import datetime
from functools import wraps
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from app import db
from models import User, Analysis

analytics_bp = Blueprint('analytics', __name__)


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected = os.environ.get('ANALYTICS_API_KEY')
        if not expected:
            logging.warning("ANALYTICS_API_KEY is not configured — analytics API is locked")
            return jsonify({'error': 'Analytics API not configured'}), 503
        if not api_key or api_key != expected:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@analytics_bp.route('/api/analytics', methods=['GET'])
@analytics_bp.route('/api/analytics/users', methods=['GET'])
@require_api_key
def analytics_users():
    total_users = User.query.count()

    analysis_stats = (
        db.session.query(
            Analysis.user_id,
            func.count(Analysis.id).label('analysis_count'),
            func.max(Analysis.created_at).label('last_analysis_created_at'),
        )
        .group_by(Analysis.user_id)
        .all()
    )

    stats_by_user = {
        row.user_id: {
            'analysis_count': row.analysis_count,
            'last_analysis_created_at': row.last_analysis_created_at,
        }
        for row in analysis_stats
    }

    users = User.query.order_by(User.created_at.desc()).all()

    user_data = []
    for user in users:
        stats = stats_by_user.get(user.id, {})
        last_analysis_dt = stats.get('last_analysis_created_at')
        user_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'signed_up_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'analysis_count': stats.get('analysis_count', 0),
            'last_analysis_created_at': last_analysis_dt.isoformat() if last_analysis_dt else None,
        })

    return jsonify({
        'total_users': total_users,
        'generated_at': datetime.utcnow().isoformat(),
        'users': user_data,
    })
