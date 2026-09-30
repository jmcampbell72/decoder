import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from models import User, Company, Subscription, CompanyInvite

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.can_access_system():
                company = user.company
                if company and company.subscription_status == 'cancelled':
                    flash('Your account has been cancelled. Please contact sales to reactivate.', 'error')
                elif company and company.subscription_status == 'trial' and company.is_trial_expired():
                    flash('Your trial period has expired. Visit our pricing page to subscribe: ', 'error')
                else:
                    flash('Your account is not active. Please contact support.', 'error')
                return render_template('login.html')

            if not user.is_active:
                flash('Your account is not active. Please contact support.', 'error')
                return render_template('login.html')

            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.username}!', 'success')

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('register.html')

        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('register.html')

        try:
            company = Company()
            company.name = f"{username}'s Workspace"
            company.subscription_status = 'trial'
            db.session.add(company)
            db.session.flush()

            subscription = Subscription()
            subscription.company_id = company.id
            subscription.tier = 'solo'
            db.session.add(subscription)

            user = User()
            user.username = username
            user.email = email
            user.password_hash = generate_password_hash(password)
            user.role = 'reviewer'
            user.company_id = company.id
            user.is_company_admin = True
            db.session.add(user)
            db.session.commit()

            send_contact_to_wix(user, company)

            flash('Registration successful! You have a 7-day trial. Please log in.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('dashboard.html', profile_mode=True)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@login_required
def reset_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([old_password, new_password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('reset_password.html')

        if not check_password_hash(current_user.password_hash, old_password):
            flash('Current password is incorrect.', 'error')
            return render_template('reset_password.html')

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'error')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('reset_password.html')

        try:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Password update failed. Please try again.', 'error')
            return render_template('reset_password.html')

    return render_template('reset_password.html')


@auth_bp.route('/invite/<token>', methods=['GET', 'POST'])
def invite_register(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    invite = CompanyInvite.query.filter_by(token=token).first()

    if not invite:
        flash('This invite link is invalid.', 'error')
        return redirect(url_for('auth.login'))

    if invite.is_used():
        flash('This invite link has already been used.', 'error')
        return redirect(url_for('auth.login'))

    company = invite.company
    subscription = company.subscription

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        if len(username) < 3:
            flash('Username must be at least 3 characters long.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

        current_count = company.get_member_count()
        if not subscription.can_add_user(current_count):
            flash('This team has reached its maximum number of members. Please contact the team admin.', 'error')
            return redirect(url_for('auth.login'))

        try:
            user = User()
            user.username = username
            user.email = email
            user.password_hash = generate_password_hash(password)
            user.role = 'reviewer'
            user.company_id = company.id
            user.is_company_admin = False
            db.session.add(user)
            db.session.flush()

            invite.used_at = datetime.utcnow()
            invite.used_by_id = user.id
            db.session.commit()

            try:
                send_contact_to_wix(user, company)
            except Exception as e:
                logging.warning(f"Wix CRM sync failed for invited user {user.email}: {e}")

            login_user(user)
            flash(f'Welcome to {company.name}! Your account has been created.', 'success')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return render_template('invite_register.html', invite=invite, company=company)

    return render_template('invite_register.html', invite=invite, company=company)
