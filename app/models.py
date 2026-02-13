"""Database models for AgriBalance."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """User model for farmers and admins."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True)  # For admin login
    password_hash = db.Column(db.String(256), nullable=True)  # For admin login
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    location = db.Column(db.String(200))
    district = db.Column(db.String(100))  # For region-wise pricing
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)  # Admin can suspend users
    language = db.Column(db.String(5), default='en')
    theme = db.Column(db.String(20), default='light')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lands = db.relationship('Land', backref='owner', lazy='dynamic')
    cultivations = db.relationship('Cultivation', backref='farmer', lazy='dynamic')
    crop_listings = db.relationship('CropListing', backref='seller', lazy='dynamic')
    posts = db.relationship('CommunityPost', backref='author', lazy='dynamic')
    
    def set_password(self, password):
        """Set hashed password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash."""
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False
    
    def __repr__(self):
        return f'<User {self.name}>'


class OTP(db.Model):
    """OTP model for mobile verification."""
    __tablename__ = 'otps'
    
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(15), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)


class Land(db.Model):
    """Land/Farm model for storing land details."""
    __tablename__ = 'lands'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    land_size = db.Column(db.Float, nullable=False)  # in acres
    land_size_unit = db.Column(db.String(20), default='acres')
    land_type = db.Column(db.String(50))  # irrigated, rain-fed, etc.
    soil_type = db.Column(db.String(50))  # clay, loam, sandy, etc.
    climate_type = db.Column(db.String(50))  # tropical, subtropical, etc.
    water_source = db.Column(db.String(100))  # well, canal, river, rain, etc.
    previous_crop = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cultivations = db.relationship('Cultivation', backref='land', lazy='dynamic')
    
    def __repr__(self):
        return f'<Land {self.name}>'


class Cultivation(db.Model):
    """Cultivation model for tracking crop cycles."""
    __tablename__ = 'cultivations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    land_id = db.Column(db.Integer, db.ForeignKey('lands.id'), nullable=False)
    crop_name = db.Column(db.String(100), nullable=False)
    variety = db.Column(db.String(100))
    area_used = db.Column(db.Float, default=0)  # Area used for this cultivation in acres
    planting_date = db.Column(db.Date)
    expected_harvest_date = db.Column(db.Date)
    actual_harvest_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='planned')  # planned, active, harvested, failed
    estimated_yield = db.Column(db.Float)
    actual_yield = db.Column(db.Float)
    yield_unit = db.Column(db.String(20), default='kg')
    ai_recommendations = db.Column(db.Text)  # JSON string of AI suggestions
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Cultivation {self.crop_name}>'


class CropListing(db.Model):
    """Crop listing for selling harvested crops."""
    __tablename__ = 'crop_listings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cultivation_id = db.Column(db.Integer, db.ForeignKey('cultivations.id'), nullable=True)
    crop_name = db.Column(db.String(100), nullable=False)
    variety = db.Column(db.String(100))
    quantity = db.Column(db.Float, nullable=False)
    quantity_unit = db.Column(db.String(20), default='kg')
    price_per_unit = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    is_organic = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='available')  # available, sold, expired
    images = db.Column(db.Text)  # JSON string of image URLs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CropListing {self.crop_name}>'


class Product(db.Model):
    """Product model for e-commerce (seeds, fertilizers, machinery)."""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # seeds, fertilizers, pesticides, machinery, tools
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    stock = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20))  # kg, liters, pieces, etc.
    brand = db.Column(db.String(100))
    images = db.Column(db.Text)  # JSON string of image URLs
    videos = db.Column(db.Text)  # JSON string of video URLs
    contact_name = db.Column(db.String(100))  # Contact person name
    contact_phone = db.Column(db.String(20))  # Contact phone number
    contact_email = db.Column(db.String(120))  # Contact email
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Product {self.name}>'


class CommunityPost(db.Model):
    """Community post model for farmer discussions."""
    __tablename__ = 'community_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # question, tip, success-story, discussion
    images = db.Column(db.Text)  # JSON string of image URLs
    videos = db.Column(db.Text)  # JSON string of video URLs
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    
    def __repr__(self):
        return f'<CommunityPost {self.title}>'


class Comment(db.Model):
    """Comment model for community posts."""
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='comments')
    
    def __repr__(self):
        return f'<Comment {self.id}>'


class NewsArticle(db.Model):
    """News article model for agriculture news and government schemes."""
    __tablename__ = 'news_articles'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    category = db.Column(db.String(50))  # news, scheme, announcement, tip
    source = db.Column(db.String(200))
    image_url = db.Column(db.String(500))
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<NewsArticle {self.title}>'


class CropPrice(db.Model):
    """Admin-managed crop prices by region/district."""
    __tablename__ = 'crop_prices'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), nullable=False)
    crop_type = db.Column(db.String(50))  # fruit, vegetable, grain, etc.
    district = db.Column(db.String(100), nullable=False)  # Region/area
    price_per_unit = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='kg')
    units_sold = db.Column(db.Integer, default=0)  # Track units sold
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CropPrice {self.crop_name} - {self.district}>'


class RegionLimit(db.Model):
    """Admin-managed region-wise area limits and crop cultivation caps."""
    __tablename__ = 'region_limits'
    
    id = db.Column(db.Integer, primary_key=True)
    district = db.Column(db.String(100), nullable=False)
    crop_name = db.Column(db.String(100), nullable=False)
    max_area = db.Column(db.Float, nullable=False)  # Maximum area in acres
    max_cultivation_count = db.Column(db.Integer, default=0)  # Max farmers allowed (0 = unlimited)
    current_area_used = db.Column(db.Float, default=0)  # Track current usage
    current_cultivation_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<RegionLimit {self.crop_name} - {self.district}>'
