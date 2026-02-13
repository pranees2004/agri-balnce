"""Admin panel routes for AgriBalance."""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Land, Cultivation, CropListing, Product, CommunityPost, NewsArticle, CropPrice, RegionLimit

admin_bp = Blueprint('admin', __name__)

# Tamil Nadu Districts for region management
TAMIL_NADU_DISTRICTS = [
    'Chennai', 'Coimbatore', 'Madurai', 'Tiruchirappalli', 'Salem',
    'Tirunelveli', 'Tiruppur', 'Erode', 'Vellore', 'Thoothukkudi',
    'Dindigul', 'Thanjavur', 'Ranipet', 'Sivaganga', 'Karur',
    'Udhagamandalam', 'Hosur', 'Nagercoil', 'Kanchipuram', 'Kumarapalayam',
    'Karaikkudi', 'Neyveli', 'Cuddalore', 'Kumbakonam', 'Tiruvannamalai',
    'Pollachi', 'Rajapalayam', 'Gudiyatham', 'Pudukkottai', 'Vaniyambadi',
    'Ambur', 'Nagapattinam', 'Other'
]

# Common crops for Tamil Nadu
COMMON_CROPS = [
    'Rice', 'Paddy', 'Sugarcane', 'Cotton', 'Groundnut', 'Banana', 'Coconut',
    'Mango', 'Tomato', 'Onion', 'Potato', 'Brinjal', 'Okra', 'Chilli',
    'Turmeric', 'Ginger', 'Tapioca', 'Maize', 'Millets', 'Pulses',
    'Grapes', 'Pomegranate', 'Papaya', 'Guava', 'Sapota', 'Orange',
    'Drumstick', 'Bitter Gourd', 'Snake Gourd', 'Bottle Gourd', 'Other'
]


def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page - accessible only at /admin/login."""
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # SECURITY NOTE: Default admin credentials (admin/admin) are for initial setup only.
        # In production, change these credentials immediately after first login or
        # configure through environment variables.
        # Check for default admin credentials or database admin
        if username == 'admin' and password == 'admin':
            # Check if admin user exists in database
            admin_user = User.query.filter_by(username='admin', is_admin=True).first()
            
            if not admin_user:
                # Create default admin user
                admin_user = User(
                    username='admin',
                    name='Administrator',
                    is_admin=True
                )
                admin_user.set_password('admin')
                db.session.add(admin_user)
                db.session.commit()
            
            login_user(admin_user)
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            # Check database for admin user
            admin_user = User.query.filter_by(username=username, is_admin=True).first()
            if admin_user and admin_user.check_password(password):
                login_user(admin_user)
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin.dashboard'))
            
            flash('Invalid admin credentials.', 'error')
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    """Admin logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system overview."""
    stats = {
        'total_users': User.query.filter_by(is_admin=False).count(),
        'total_lands': Land.query.count(),
        'active_cultivations': Cultivation.query.filter_by(status='active').count(),
        'crop_listings': CropListing.query.filter_by(status='available').count(),
        'products': Product.query.count(),
        'community_posts': CommunityPost.query.count(),
        'news_articles': NewsArticle.query.count()
    }
    
    recent_users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).limit(5).all()
    recent_listings = CropListing.query.order_by(CropListing.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_users=recent_users,
        recent_listings=recent_listings
    )


# User Management
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """List all users."""
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def view_user(user_id):
    """View user details."""
    user = User.query.get_or_404(user_id)
    return render_template('admin/view_user.html', user=user)


@admin_bp.route('/users/<int:user_id>/toggle-suspend', methods=['POST'])
@login_required
@admin_required
def toggle_suspend(user_id):
    """Toggle user suspension status."""
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot suspend admin users.', 'error')
    else:
        user.is_suspended = not user.is_suspended
        db.session.commit()
        status = 'suspended' if user.is_suspended else 'activated'
        flash(f'User {user.name} has been {status}.', 'success')
    
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user."""
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot delete admin users.', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.name} deleted.', 'success')
    
    return redirect(url_for('admin.users'))


# Crop Price Management
@admin_bp.route('/prices')
@login_required
@admin_required
def prices():
    """List all crop prices."""
    crop_prices = CropPrice.query.order_by(CropPrice.crop_name, CropPrice.district).all()
    return render_template('admin/prices.html', prices=crop_prices)


@admin_bp.route('/prices/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_price():
    """Add new crop price."""
    if request.method == 'POST':
        crop_price = CropPrice(
            crop_name=request.form.get('crop_name'),
            crop_type=request.form.get('crop_type'),
            district=request.form.get('district'),
            price_per_unit=float(request.form.get('price_per_unit', 0)),
            unit=request.form.get('unit', 'kg'),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(crop_price)
        db.session.commit()
        
        flash('Crop price added successfully!', 'success')
        return redirect(url_for('admin.prices'))
    
    return render_template(
        'admin/add_price.html',
        districts=TAMIL_NADU_DISTRICTS,
        crops=COMMON_CROPS
    )


@admin_bp.route('/prices/<int:price_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_price(price_id):
    """Edit crop price."""
    crop_price = CropPrice.query.get_or_404(price_id)
    
    if request.method == 'POST':
        crop_price.crop_name = request.form.get('crop_name', crop_price.crop_name)
        crop_price.crop_type = request.form.get('crop_type', crop_price.crop_type)
        crop_price.district = request.form.get('district', crop_price.district)
        crop_price.price_per_unit = float(request.form.get('price_per_unit', crop_price.price_per_unit))
        crop_price.unit = request.form.get('unit', crop_price.unit)
        crop_price.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Crop price updated!', 'success')
        return redirect(url_for('admin.prices'))
    
    return render_template(
        'admin/edit_price.html',
        price=crop_price,
        districts=TAMIL_NADU_DISTRICTS,
        crops=COMMON_CROPS
    )


@admin_bp.route('/prices/<int:price_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_price(price_id):
    """Delete crop price."""
    crop_price = CropPrice.query.get_or_404(price_id)
    db.session.delete(crop_price)
    db.session.commit()
    flash('Crop price deleted!', 'success')
    return redirect(url_for('admin.prices'))


# Region Limits Management
@admin_bp.route('/limits')
@login_required
@admin_required
def limits():
    """List all region limits."""
    region_limits = RegionLimit.query.order_by(RegionLimit.district, RegionLimit.crop_name).all()
    return render_template('admin/limits.html', limits=region_limits)


@admin_bp.route('/limits/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_limit():
    """Add new region limit."""
    if request.method == 'POST':
        region_limit = RegionLimit(
            district=request.form.get('district'),
            crop_name=request.form.get('crop_name'),
            max_area=float(request.form.get('max_area', 0)),
            max_cultivation_count=int(request.form.get('max_cultivation_count', 0)),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(region_limit)
        db.session.commit()
        
        flash('Region limit added successfully!', 'success')
        return redirect(url_for('admin.limits'))
    
    return render_template(
        'admin/add_limit.html',
        districts=TAMIL_NADU_DISTRICTS,
        crops=COMMON_CROPS
    )


@admin_bp.route('/limits/<int:limit_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_limit(limit_id):
    """Edit region limit."""
    region_limit = RegionLimit.query.get_or_404(limit_id)
    
    if request.method == 'POST':
        region_limit.district = request.form.get('district', region_limit.district)
        region_limit.crop_name = request.form.get('crop_name', region_limit.crop_name)
        region_limit.max_area = float(request.form.get('max_area', region_limit.max_area))
        region_limit.max_cultivation_count = int(request.form.get('max_cultivation_count', region_limit.max_cultivation_count))
        region_limit.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Region limit updated!', 'success')
        return redirect(url_for('admin.limits'))
    
    return render_template(
        'admin/edit_limit.html',
        limit=region_limit,
        districts=TAMIL_NADU_DISTRICTS,
        crops=COMMON_CROPS
    )


@admin_bp.route('/limits/<int:limit_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_limit(limit_id):
    """Delete region limit."""
    region_limit = RegionLimit.query.get_or_404(limit_id)
    db.session.delete(region_limit)
    db.session.commit()
    flash('Region limit deleted!', 'success')
    return redirect(url_for('admin.limits'))


# Product Management
@admin_bp.route('/products')
@login_required
@admin_required
def products():
    """List all products."""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)


@admin_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    """Add new product."""
    if request.method == 'POST':
        product = Product(
            name=request.form.get('name'),
            category=request.form.get('category'),
            description=request.form.get('description'),
            price=float(request.form.get('price', 0)),
            stock=int(request.form.get('stock', 0)),
            unit=request.form.get('unit'),
            brand=request.form.get('brand'),
            images=request.form.get('images'),
            videos=request.form.get('videos'),
            contact_name=request.form.get('contact_name'),
            contact_phone=request.form.get('contact_phone'),
            contact_email=request.form.get('contact_email'),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    categories = ['seeds', 'fertilizers', 'pesticides', 'machinery', 'tools']
    return render_template('admin/add_product.html', categories=categories)


@admin_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    """Edit product."""
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name', product.name)
        product.category = request.form.get('category', product.category)
        product.description = request.form.get('description', product.description)
        product.price = float(request.form.get('price', product.price))
        product.stock = int(request.form.get('stock', product.stock))
        product.unit = request.form.get('unit', product.unit)
        product.brand = request.form.get('brand', product.brand)
        product.images = request.form.get('images', product.images)
        product.videos = request.form.get('videos', product.videos)
        product.contact_name = request.form.get('contact_name', product.contact_name)
        product.contact_phone = request.form.get('contact_phone', product.contact_phone)
        product.contact_email = request.form.get('contact_email', product.contact_email)
        product.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('admin.products'))
    
    categories = ['seeds', 'fertilizers', 'pesticides', 'machinery', 'tools']
    return render_template('admin/edit_product.html', product=product, categories=categories)


@admin_bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    """Delete product."""
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted!', 'success')
    return redirect(url_for('admin.products'))


# News/Content Management
@admin_bp.route('/news')
@login_required
@admin_required
def news():
    """List all news articles."""
    articles = NewsArticle.query.order_by(NewsArticle.created_at.desc()).all()
    return render_template('admin/news.html', articles=articles)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_news():
    """Add news article."""
    if request.method == 'POST':
        article = NewsArticle(
            title=request.form.get('title'),
            content=request.form.get('content'),
            summary=request.form.get('summary'),
            category=request.form.get('category'),
            source=request.form.get('source'),
            image_url=request.form.get('image_url'),
            is_featured=request.form.get('is_featured') == 'on',
            is_published=request.form.get('is_published') == 'on'
        )
        db.session.add(article)
        db.session.commit()
        
        flash('Article added successfully!', 'success')
        return redirect(url_for('admin.news'))
    
    categories = ['news', 'scheme', 'announcement', 'tip']
    return render_template('admin/add_news.html', categories=categories)


@admin_bp.route('/news/<int:article_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_news(article_id):
    """Edit news article."""
    article = NewsArticle.query.get_or_404(article_id)
    
    if request.method == 'POST':
        article.title = request.form.get('title', article.title)
        article.content = request.form.get('content', article.content)
        article.summary = request.form.get('summary', article.summary)
        article.category = request.form.get('category', article.category)
        article.source = request.form.get('source', article.source)
        article.image_url = request.form.get('image_url', article.image_url)
        article.is_featured = request.form.get('is_featured') == 'on'
        article.is_published = request.form.get('is_published') == 'on'
        
        db.session.commit()
        flash('Article updated!', 'success')
        return redirect(url_for('admin.news'))
    
    categories = ['news', 'scheme', 'announcement', 'tip']
    return render_template('admin/edit_news.html', article=article, categories=categories)


@admin_bp.route('/news/<int:article_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_news(article_id):
    """Delete news article."""
    article = NewsArticle.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    flash('Article deleted!', 'success')
    return redirect(url_for('admin.news'))


# Community Moderation
@admin_bp.route('/community')
@login_required
@admin_required
def community_posts():
    """List all community posts for moderation."""
    posts = CommunityPost.query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('admin/community.html', posts=posts)


@admin_bp.route('/community/<int:post_id>/pin', methods=['POST'])
@login_required
@admin_required
def pin_post(post_id):
    """Toggle post pinned status."""
    post = CommunityPost.query.get_or_404(post_id)
    post.is_pinned = not post.is_pinned
    db.session.commit()
    flash(f'Post {"pinned" if post.is_pinned else "unpinned"}!', 'success')
    return redirect(url_for('admin.community_posts'))


@admin_bp.route('/community/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_post(post_id):
    """Delete a community post."""
    post = CommunityPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted!', 'success')
    return redirect(url_for('admin.community_posts'))


# Listings Management
@admin_bp.route('/listings')
@login_required
@admin_required
def listings():
    """List all crop listings."""
    listings = CropListing.query.order_by(CropListing.created_at.desc()).all()
    return render_template('admin/listings.html', listings=listings)


@admin_bp.route('/listings/<int:listing_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_listing(listing_id):
    """Delete a crop listing."""
    listing = CropListing.query.get_or_404(listing_id)
    db.session.delete(listing)
    db.session.commit()
    flash('Listing deleted!', 'success')
    return redirect(url_for('admin.listings'))


# Cultivations Management
@admin_bp.route('/cultivations')
@login_required
@admin_required
def cultivations():
    """List all cultivations."""
    cultivations = Cultivation.query.order_by(Cultivation.created_at.desc()).all()
    return render_template('admin/cultivations.html', cultivations=cultivations)


# Lands Management
@admin_bp.route('/lands')
@login_required
@admin_required
def lands():
    """List all lands."""
    lands = Land.query.order_by(Land.created_at.desc()).all()
    return render_template('admin/lands.html', lands=lands)
