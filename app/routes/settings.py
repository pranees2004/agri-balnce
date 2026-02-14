"""Settings routes for AgriBalance."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user, logout_user
from app import db

settings_bp = Blueprint('settings', __name__)


# Supported languages
LANGUAGES = {
    'en': 'English',
    'hi': 'हिंदी (Hindi)',
    'ta': 'தமிழ் (Tamil)',
    'te': 'తెలుగు (Telugu)',
    'bn': 'বাংলা (Bengali)',
    'mr': 'मराठी (Marathi)',
    'gu': 'ગુજરાતી (Gujarati)',
    'kn': 'ಕನ್ನಡ (Kannada)',
    'ml': 'മലയാളം (Malayalam)',
    'pa': 'ਪੰਜਾਬੀ (Punjabi)'
}

THEMES = {
    'light': 'Light Theme',
    'dark': 'Dark Theme',
    'green': 'Green Theme'
}


@settings_bp.route('/')
@login_required
def index():
    """Settings page."""
    return render_template(
        'settings/index.html',
        languages=LANGUAGES,
        themes=THEMES
    )


@settings_bp.route('/language', methods=['POST'])
@login_required
def change_language():
    """Change user language preference."""
    language = request.form.get('language', 'en')
    
    if language in LANGUAGES:
        current_user.language = language
        db.session.commit()
        flash(f'Language changed to {LANGUAGES[language]}', 'success')
    else:
        flash('Invalid language selection.', 'error')
    
    return redirect(url_for('settings.index'))


@settings_bp.route('/theme', methods=['POST'])
@login_required
def change_theme():
    """Change user theme preference."""
    theme = request.form.get('theme', 'light')
    
    if theme in THEMES:
        current_user.theme = theme
        db.session.commit()
        flash(f'Theme changed to {THEMES[theme]}', 'success')
    else:
        flash('Invalid theme selection.', 'error')
    
    return redirect(url_for('settings.index'))


@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    """Update user profile."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        location = request.form.get('location')
        
        if name:
            current_user.name = name
        if email:
            current_user.email = email
        current_user.location = location
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('settings.index'))
    
    return render_template('settings/profile.html')


@settings_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account."""
    confirm = request.form.get('confirm')
    
    if confirm == 'DELETE':
        # Delete user and related data
        user = current_user
        db.session.delete(user)
        db.session.commit()
        flash('Your account has been deleted.', 'info')
        return redirect(url_for('main.index'))
    
    flash('Account deletion cancelled.', 'info')
    return redirect(url_for('settings.index'))


@settings_bp.route('/logout')
@login_required
def logout():
    """Logout user."""
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('main.index'))
