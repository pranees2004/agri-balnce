"""Main routes for AgriBalance - Welcome page."""
from flask import Blueprint, render_template, session, jsonify

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Welcome page with login/register options and language selection."""
    return render_template('index.html')


@main_bp.route('/about')
def about():
    """About page."""
    return render_template('about.html')


@main_bp.route('/set-language/<lang>', methods=['POST'])
def set_language(lang):
    """Set language preference in session (for non-authenticated users)."""
    supported_languages = ['en', 'ta', 'hi', 'te', 'kn', 'ml', 'bn', 'mr', 'gu', 'pa']
    if lang in supported_languages:
        session['language'] = lang
        return jsonify({'success': True, 'language': lang})
    return jsonify({'success': False, 'error': 'Unsupported language'}), 400
