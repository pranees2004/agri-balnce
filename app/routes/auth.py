"""Authentication routes for AgriBalance."""
import random
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, OTP

auth_bp = Blueprint('auth', __name__)


def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with mobile OTP or Google login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        name = request.form.get('name')
        
        if mobile:
            # Check if user exists
            user = User.query.filter_by(mobile=mobile).first()
            
            if user:
                # Generate and store OTP
                otp_code = generate_otp()
                otp = OTP(
                    mobile=mobile,
                    otp_code=otp_code,
                    expires_at=datetime.utcnow() + timedelta(minutes=5)
                )
                db.session.add(otp)
                db.session.commit()
                
                # In production, send OTP via SMS
                # For demo, we'll store it in session
                session['pending_otp'] = otp_code
                session['pending_mobile'] = mobile
                
                flash(f'OTP sent to {mobile}. For demo: {otp_code}', 'info')
                return redirect(url_for('auth.verify_otp'))
            else:
                flash('Mobile number not registered. Please register first.', 'warning')
                return redirect(url_for('auth.register'))
    
    return render_template('auth/login.html')


@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """Verify OTP for login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    mobile = session.get('pending_mobile')
    if not mobile:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        
        # Verify OTP
        otp = OTP.query.filter_by(
            mobile=mobile,
            otp_code=entered_otp,
            is_used=False
        ).first()
        
        if otp and otp.expires_at > datetime.utcnow():
            otp.is_used = True
            db.session.commit()
            
            # Login user
            user = User.query.filter_by(mobile=mobile).first()
            if user:
                login_user(user)
                session.pop('pending_otp', None)
                session.pop('pending_mobile', None)
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
    
    return render_template('auth/verify_otp.html', mobile=mobile)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        location = request.form.get('location')
        
        # Validate required fields
        if not name or not mobile:
            flash('Name and mobile number are required.', 'error')
            return render_template('auth/register.html')
        
        # Check if user already exists
        existing_user = User.query.filter_by(mobile=mobile).first()
        if existing_user:
            flash('Mobile number already registered. Please login.', 'warning')
            return redirect(url_for('auth.login'))
        
        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash('Email already registered.', 'warning')
                return render_template('auth/register.html')
        
        # Create new user
        user = User(
            name=name,
            mobile=mobile,
            email=email if email else None,
            location=location
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')


@auth_bp.route('/google-login')
def google_login():
    """Initiate Google OAuth login."""
    # In production, implement proper Google OAuth
    flash('Google login will be available soon.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
