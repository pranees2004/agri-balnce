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
    taluk = db.Column(db.String(100))  # Taluk/Tehsil for granular location
    village = db.Column(db.String(100))  # Village name
    latitude = db.Column(db.Float)  # GPS latitude
    longitude = db.Column(db.Float)  # GPS longitude
    land_size = db.Column(db.Float, nullable=False)  # in acres
    land_size_unit = db.Column(db.String(20), default='acres')
    land_type = db.Column(db.String(50))  # Wetland, Dryland
    soil_type = db.Column(db.String(50))  # Red, Black, Alluvial, Sandy, Clay
    climate_type = db.Column(db.String(50))  # Tropical, Semi-Arid, Humid
    water_source = db.Column(db.String(100))  # Rain-fed, Borewell, Canal, Tank
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
    cultivation_approval_id = db.Column(db.String(50), unique=True, nullable=True)  # Unique approval ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    land_id = db.Column(db.Integer, db.ForeignKey('lands.id'), nullable=False)
    quota_id = db.Column(db.Integer, db.ForeignKey('admin_quotas.id'), nullable=True)  # Link to quota
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
    max_allowed_sale_quantity = db.Column(db.Float)  # Maximum quantity allowed for sale
    ai_recommendations = db.Column(db.Text)  # JSON string of AI suggestions
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    harvest_sales = db.relationship('HarvestSale', backref='cultivation', lazy='dynamic')
    
    def validate_harvest_submission(self, harvest_date, harvest_quantity, tolerance=0.10):
        """Validate harvest submission against quota rules and estimated yield.
        
        Args:
            harvest_date: Date of harvest
            harvest_quantity: Quantity being harvested
            tolerance: Allowed tolerance percentage (default 10%)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check if harvest date is within quota harvest window
        if self.quota:
            if self.quota.harvest_season_start and self.quota.harvest_season_end:
                if isinstance(harvest_date, str):
                    harvest_date = datetime.strptime(harvest_date, '%Y-%m-%d').date()
                
                if not (self.quota.harvest_season_start <= harvest_date <= self.quota.harvest_season_end):
                    return False, f"Harvest date must be between {self.quota.harvest_season_start} and {self.quota.harvest_season_end}"
        
        # Check if cultivation is active
        if self.status not in ['planned', 'active']:
            return False, "Only active cultivations can be harvested"
        
        # Validate quantity against estimated yield (with tolerance)
        if self.estimated_yield:
            max_allowed = self.estimated_yield * (1 + tolerance)
            if harvest_quantity > max_allowed:
                return False, f"Harvest quantity ({harvest_quantity} {self.yield_unit}) exceeds estimated yield ({self.estimated_yield} {self.yield_unit}) plus {tolerance*100}% tolerance"
        
        return True, None
    
    def cancel_cultivation(self):
        """Cancel cultivation and release quota allocation."""
        if self.status == 'harvested':
            raise ValueError("Cannot cancel harvested cultivation")
        
        # Release quota allocation
        if self.quota:
            self.quota.release_area(self.area_used, decrement_farmer_count=True)
        
        # Update legacy RegionLimit if used
        if self.land and self.land.district:
            from app.models import RegionLimit
            region_limit = RegionLimit.query.filter_by(
                crop_name=self.crop_name,
                district=self.land.district,
                is_active=True
            ).first()
            if region_limit:
                region_limit.current_area_used = max(0, region_limit.current_area_used - self.area_used)
                region_limit.current_cultivation_count = max(0, region_limit.current_cultivation_count - 1)
        
        self.status = 'cancelled'
        self.updated_at = datetime.utcnow()
    
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
    """Admin-managed crop prices by region/district with time periods."""
    __tablename__ = 'crop_prices'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), nullable=False)
    crop_type = db.Column(db.String(50))  # fruit, vegetable, grain, etc.
    district = db.Column(db.String(100), nullable=False)  # Region/area
    price_per_unit = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='kg')
    units_sold = db.Column(db.Integer, default=0)  # Track units sold
    # Period fields for time-based pricing
    valid_from = db.Column(db.Date, nullable=True)  # Start date of price validity
    valid_to = db.Column(db.Date, nullable=True)  # End date of price validity
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CropPrice {self.crop_name} - {self.district}>'


class RegionLimit(db.Model):
    """Admin-managed region-wise area limits and crop cultivation caps (DEPRECATED - use AdminQuota)."""
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


class CropMaster(db.Model):
    """Master table for standard crop information."""
    __tablename__ = 'crop_master'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), unique=True, nullable=False)
    crop_type = db.Column(db.String(50))  # Grain, Vegetable, Fruit, Pulse, Oilseed, etc.
    scientific_name = db.Column(db.String(200))
    avg_yield_per_acre = db.Column(db.Float)  # Average yield per acre
    yield_unit = db.Column(db.String(20), default='kg')
    growth_duration_days = db.Column(db.Integer)  # Typical growth period
    water_requirement = db.Column(db.String(50))  # Low, Medium, High
    suitable_soil_types = db.Column(db.Text)  # JSON array of suitable soils
    suitable_climate_types = db.Column(db.Text)  # JSON array of suitable climates
    season = db.Column(db.String(50))  # Kharif, Rabi, Zaid, Year-round
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CropMaster {self.crop_name}>'


class AdminQuota(db.Model):
    """Admin-controlled crop cultivation quotas based on location and season."""
    __tablename__ = 'admin_quotas'
    
    id = db.Column(db.Integer, primary_key=True)
    # Geographic scope
    country = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    taluk = db.Column(db.String(100))
    village = db.Column(db.String(100))
    # GPS polygon for advanced location (stored as JSON)
    gps_polygon = db.Column(db.Text)
    
    # Crop details
    crop_name = db.Column(db.String(100), nullable=False)
    
    # Harvest season
    harvest_season_start = db.Column(db.Date)
    harvest_season_end = db.Column(db.Date)
    
    # Quota limits
    total_allowed_area = db.Column(db.Float, nullable=False)  # in acres/hectares
    area_unit = db.Column(db.String(20), default='acres')
    max_per_farmer = db.Column(db.Float)  # Optional: max area per farmer
    
    # Current allocation tracking
    allocated_area = db.Column(db.Float, default=0)  # Currently allocated
    allocated_farmer_count = db.Column(db.Integer, default=0)
    
    # Market demand integration
    predicted_demand_volume = db.Column(db.Float)
    expected_harvest_volume = db.Column(db.Float)
    
    # Price guidance
    min_price_per_unit = db.Column(db.Float)
    max_price_per_unit = db.Column(db.Float)
    price_unit = db.Column(db.String(20), default='kg')
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cultivations = db.relationship('Cultivation', backref='quota', lazy='dynamic')
    
    def remaining_area(self):
        """Calculate remaining available area."""
        return self.total_allowed_area - self.allocated_area
    
    def is_quota_available(self, requested_area, farmer_id=None):
        """Check if quota is available for requested area."""
        if not self.is_active:
            return False, "Quota is not active"
        
        # Calculate remaining once to avoid race conditions
        remaining = self.remaining_area()
        if remaining < requested_area:
            return False, f"Only {remaining:.2f} {self.area_unit} available"
        
        if self.max_per_farmer and requested_area > self.max_per_farmer:
            return False, f"Maximum {self.max_per_farmer} {self.area_unit} per farmer"
        
        return True, "Quota available"
    
    def check_per_farmer_limit(self, farmer_id, requested_area):
        """Check if farmer has not exceeded per-farmer limit for this crop."""
        if not self.max_per_farmer:
            return True, "No per-farmer limit set"
        
        # Calculate farmer's existing allocation for this quota
        from sqlalchemy import func
        existing_area = db.session.query(
            func.coalesce(func.sum(Cultivation.area_used), 0)
        ).filter(
            Cultivation.quota_id == self.id,
            Cultivation.user_id == farmer_id,
            Cultivation.status.in_(['planned', 'active', 'harvested'])
        ).scalar()
        
        total_requested = existing_area + requested_area
        
        if total_requested > self.max_per_farmer:
            return False, f"Per-farmer limit exceeded. Current: {existing_area:.2f} {self.area_unit}, Requested: {requested_area:.2f} {self.area_unit}, Limit: {self.max_per_farmer:.2f} {self.area_unit}"
        
        return True, "Within per-farmer limit"
    
    def is_within_harvest_window(self, cultivation_start_date, cultivation_end_date):
        """Check if cultivation dates are within the harvest window."""
        if not self.harvest_season_start or not self.harvest_season_end:
            return True, "No harvest window restriction"
        
        # Convert string dates to date objects if necessary
        if isinstance(cultivation_start_date, str):
            cultivation_start_date = datetime.strptime(cultivation_start_date, '%Y-%m-%d').date()
        if isinstance(cultivation_end_date, str):
            cultivation_end_date = datetime.strptime(cultivation_end_date, '%Y-%m-%d').date()
        
        # Check if cultivation dates are within harvest window
        if cultivation_start_date < self.harvest_season_start:
            return False, f"Cultivation start date must be on or after {self.harvest_season_start}"
        
        if cultivation_end_date > self.harvest_season_end:
            return False, f"Expected harvest date must be on or before {self.harvest_season_end}"
        
        return True, "Within harvest window"
    
    def allocate_area(self, area, increment_farmer_count=True):
        """Allocate area from quota (should be called within transaction)."""
        if self.allocated_area + area > self.total_allowed_area:
            raise ValueError(f"Cannot allocate {area} {self.area_unit}. Would exceed total limit.")
        
        self.allocated_area += area
        if increment_farmer_count:
            self.allocated_farmer_count += 1
        self.updated_at = datetime.utcnow()
    
    def release_area(self, area, decrement_farmer_count=True):
        """Release area back to quota (for cultivation cancellation)."""
        self.allocated_area = max(0, self.allocated_area - area)
        if decrement_farmer_count:
            self.allocated_farmer_count = max(0, self.allocated_farmer_count - 1)
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<AdminQuota {self.crop_name} - {self.district}>'


class HarvestSale(db.Model):
    """Harvest sales submissions for admin approval."""
    __tablename__ = 'harvest_sales'
    
    id = db.Column(db.Integer, primary_key=True)
    cultivation_id = db.Column(db.Integer, db.ForeignKey('cultivations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Harvest details
    actual_yield_quantity = db.Column(db.Float, nullable=False)
    yield_unit = db.Column(db.String(20), default='kg')
    
    # Selling details
    selling_quantity = db.Column(db.Float, nullable=False)
    approved_quantity = db.Column(db.Float)  # Admin can adjust
    selling_price_expectation = db.Column(db.Float)
    contact_number = db.Column(db.String(20))
    
    # Photos
    photos = db.Column(db.Text)  # JSON array of photo URLs
    
    # Admin approval
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    farmer = db.relationship('User', foreign_keys=[user_id], backref='harvest_submissions')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def get_remaining_quantity(self):
        """Calculate remaining quantity available for sale."""
        if self.approved_quantity is not None:
            return self.approved_quantity
        return self.actual_yield_quantity
    
    def validate_sale_quantity(self, requested_sale_quantity):
        """Validate that sale quantity doesn't exceed remaining harvest quantity."""
        remaining = self.get_remaining_quantity()
        if requested_sale_quantity > remaining:
            return False, f"Sale quantity ({requested_sale_quantity} {self.yield_unit}) exceeds remaining harvest quantity ({remaining} {self.yield_unit})"
        return True, None
    
    def __repr__(self):
        return f'<HarvestSale {self.id} - {self.status}>'


class MarketDemandData(db.Model):
    """Market demand predictions and trends."""
    __tablename__ = 'market_demand_data'
    
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100))
    state = db.Column(db.String(100))
    
    # Demand predictions
    predicted_demand = db.Column(db.Float)  # in tonnes
    predicted_supply = db.Column(db.Float)  # in tonnes
    demand_supply_ratio = db.Column(db.Float)
    
    # Price trends
    current_price = db.Column(db.Float)
    predicted_price = db.Column(db.Float)
    price_unit = db.Column(db.String(20), default='kg')
    
    # Time period
    forecast_date = db.Column(db.Date)
    season = db.Column(db.String(50))
    
    # Confidence
    confidence_score = db.Column(db.Float)  # 0-1 scale
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MarketDemand {self.crop_name} - {self.district}>'


class Notification(db.Model):
    """Notifications for admin-farmer communications."""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Notification details
    notification_type = db.Column(db.String(50), nullable=False)  # harvest_submitted, quota_alert, approval, rejection
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Related entities
    related_cultivation_id = db.Column(db.Integer, db.ForeignKey('cultivations.id'))
    related_harvest_sale_id = db.Column(db.Integer, db.ForeignKey('harvest_sales.id'))
    
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.title}>'


class Message(db.Model):
    """Direct messages between users."""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    
    def __repr__(self):
        return f'<Message {self.id}>'


class ProductOrder(db.Model):
    """Product orders from users to admin."""
    __tablename__ = 'product_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='product_orders')
    product = db.relationship('Product', backref='orders')
    
    def __repr__(self):
        return f'<ProductOrder {self.id} - {self.status}>'
