"""Dashboard routes for AgriBalance."""
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Land, Cultivation, CropListing, CropPrice

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard with quick access buttons."""
    # Get user's data summary
    lands_count = Land.query.filter_by(user_id=current_user.id).count()
    active_cultivations = Cultivation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).count()
    active_listings = CropListing.query.filter_by(
        user_id=current_user.id,
        status='available'
    ).count()
    
    # Get today's crop prices
    crop_prices = CropPrice.query.filter_by(is_active=True).order_by(
        CropPrice.crop_name
    ).all()
    
    return render_template(
        'dashboard/index.html',
        lands_count=lands_count,
        active_cultivations=active_cultivations,
        active_listings=active_listings,
        crop_prices=crop_prices
    )


@dashboard_bp.route('/profile')
@login_required
def profile():
    """User profile page with posts and platform rules."""
    from app.models import CommunityPost
    user_posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(
        CommunityPost.created_at.desc()
    ).limit(10).all()
    return render_template('dashboard/profile.html', user_posts=user_posts)
