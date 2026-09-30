import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app import db
from models import User, CompanyInvite

logger = logging.getLogger(__name__)

team_bp = Blueprint('team', __name__)


def _require_company_admin():
    if not current_user.is_company_admin:
        flash('Team admin access is only available to company workspace owners.', 'error')
        return redirect(url_for('main.dashboard'))
    if not current_user.company_id:
        flash('You are not associated with a company workspace.', 'error')
        return redirect(url_for('main.dashboard'))
    return None


@team_bp.route('/admin')
@login_required
def admin():
    guard = _require_company_admin()
    if guard:
        return guard

    company = current_user.company
    subscription = company.subscription
    members = User.query.filter_by(company_id=company.id).order_by(User.created_at).all()
    invites = CompanyInvite.query.filter_by(company_id=company.id, used_at=None).order_by(CompanyInvite.created_at.desc()).all()

    new_invite_url = session.pop('new_invite_url', None)

    return render_template(
        'team_admin.html',
        company=company,
        subscription=subscription,
        members=members,
        invites=invites,
        new_invite_url=new_invite_url,
        member_count=len(members),
    )


@team_bp.route('/invite', methods=['POST'])
@login_required
def create_invite():
    guard = _require_company_admin()
    if guard:
        return guard

    company = current_user.company
    subscription = company.subscription

    if not subscription.allows_team():
        flash('Invite links require a Team or Enterprise subscription.', 'error')
        return redirect(url_for('team.admin'))

    current_count = company.get_member_count()
    if not subscription.can_add_user(current_count):
        flash(f'Your team is at its seat limit ({subscription.max_seats()} seats). Upgrade to Enterprise for unlimited seats.', 'error')
        return redirect(url_for('team.admin'))

    invited_email = request.form.get('invited_email', '').strip().lower() or None

    try:
        invite = CompanyInvite()
        invite.company_id = company.id
        invite.token = CompanyInvite.generate_token()
        invite.invited_email = invited_email
        invite.created_by_id = current_user.id
        db.session.add(invite)
        db.session.commit()

        invite_url = url_for('auth.invite_register', token=invite.token, _external=True)
        session['new_invite_url'] = invite_url
        flash('Invite link generated successfully!', 'success')
        logger.info(f"Invite created by {current_user.email} for company {company.id}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create invite: {e}")
        flash('Failed to generate invite link. Please try again.', 'error')

    return redirect(url_for('team.admin'))


@team_bp.route('/rename', methods=['POST'])
@login_required
def rename_company():
    guard = _require_company_admin()
    if guard:
        return guard

    new_name = request.form.get('company_name', '').strip()

    if not new_name:
        flash('Company name cannot be empty.', 'error')
        return redirect(url_for('team.admin'))

    if len(new_name) > 100:
        flash('Company name must be 100 characters or fewer.', 'error')
        return redirect(url_for('team.admin'))

    try:
        company = current_user.company
        old_name = company.name
        company.name = new_name
        db.session.commit()
        flash(f'Workspace renamed from "{old_name}" to "{new_name}".', 'success')
        logger.info(f"Company {company.id} renamed to '{new_name}' by {current_user.email}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to rename company: {e}")
        flash('Failed to rename workspace. Please try again.', 'error')

    return redirect(url_for('team.admin'))


@team_bp.route('/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
def toggle_admin(user_id):
    guard = _require_company_admin()
    if guard:
        return guard

    if user_id == current_user.id:
        flash('You cannot change your own Team Admin role.', 'error')
        return redirect(url_for('team.admin'))

    target = User.query.get_or_404(user_id)

    if target.company_id != current_user.company_id:
        flash('This user is not a member of your team.', 'error')
        return redirect(url_for('team.admin'))

    if target.is_company_admin:
        admins_remaining = User.query.filter_by(
            company_id=current_user.company_id,
            is_company_admin=True
        ).count()
        if admins_remaining <= 1:
            flash('Cannot demote the last Team Admin. Promote another member first.', 'error')
            return redirect(url_for('team.admin'))
        target.is_company_admin = False
        action = 'demoted to Member'
    else:
        target.is_company_admin = True
        action = 'promoted to Team Admin'

    try:
        db.session.commit()
        flash(f'{target.username} has been {action}.', 'success')
        logger.info(f"User {target.email} {action} in company {current_user.company_id} by {current_user.email}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to toggle admin: {e}")
        flash('Failed to update role. Please try again.', 'error')

    return redirect(url_for('team.admin'))


@team_bp.route('/invite/<int:invite_id>/delete', methods=['POST'])
@login_required
def delete_invite(invite_id):
    guard = _require_company_admin()
    if guard:
        return guard

    invite = CompanyInvite.query.get_or_404(invite_id)

    if invite.company_id != current_user.company_id:
        flash('This invite does not belong to your team.', 'error')
        return redirect(url_for('team.admin'))

    if invite.used_at is not None:
        flash('This invite has already been used and cannot be deleted.', 'error')
        return redirect(url_for('team.admin'))

    try:
        db.session.delete(invite)
        db.session.commit()
        flash('Invite has been cancelled successfully.', 'success')
        logger.info(f"Invite {invite_id} deleted by {current_user.email} for company {current_user.company_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete invite {invite_id}: {e}")
        flash('Failed to cancel invite. Please try again.', 'error')

    return redirect(url_for('team.admin'))


@team_bp.route('/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_member(user_id):
    guard = _require_company_admin()
    if guard:
        return guard

    if user_id == current_user.id:
        flash('You cannot remove yourself from the team.', 'error')
        return redirect(url_for('team.admin'))

    user = User.query.get_or_404(user_id)

    if user.company_id != current_user.company_id:
        flash('This user is not a member of your team.', 'error')
        return redirect(url_for('team.admin'))

    try:
        user.company_id = None
        user.is_company_admin = False
        db.session.commit()
        flash(f'{user.username} has been removed from the team.', 'success')
        logger.info(f"User {user.email} removed from company {current_user.company_id} by {current_user.email}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to remove user: {e}")
        flash('Failed to remove user. Please try again.', 'error')

    return redirect(url_for('team.admin'))
