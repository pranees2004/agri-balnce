"""Selling/Marketplace routes for AgriBalance."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import CropListing, Cultivation, CropPrice

selling_bp = Blueprint('selling', __name__)

# Tolerance for quantity changes after harvest (5% - allows for minor measurement variations)
QUANTITY_TOLERANCE = 0.05


def get_crop_price(crop_name, district):
    """Get admin-set price for a crop in a district."""
    price = CropPrice.query.filter_by(
        crop_name=crop_name,
        district=district,
        is_active=True
    ).first()
    return price


@selling_bp.route('/')
@login_required
def marketplace():
    """View crop marketplace - all available listings."""
    listings = CropListing.query.filter_by(status='available').order_by(
        CropListing.created_at.desc()
    ).all()
    return render_template('selling/marketplace.html', listings=listings)


@selling_bp.route('/my-listings')
@login_required
def my_listings():
    """View user's own crop listings."""
    listings = CropListing.query.filter_by(user_id=current_user.id).order_by(
        CropListing.created_at.desc()
    ).all()
    return render_template('selling/my_listings.html', listings=listings)


@selling_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_listing():
    """Add new crop listing - only from cultivated crops."""
    # Get user's harvested cultivations - farmers can only sell their own cultivated crops
    harvested_cultivations = Cultivation.query.filter_by(
        user_id=current_user.id,
        status='harvested'
    ).all()
    
    if not harvested_cultivations:
        flash('You can only sell crops from your own cultivations. Please complete a harvest first.', 'warning')
        return redirect(url_for('cultivation.list_cultivations'))
    
    if request.method == 'POST':
        cultivation_id = request.form.get('cultivation_id')
        quantity = request.form.get('quantity')
        
        if not cultivation_id:
            flash('Please select a cultivation to sell from.', 'error')
            return render_template('selling/add_listing.html', 
                                   cultivations=harvested_cultivations)
        
        # Get the cultivation
        cultivation = Cultivation.query.filter_by(
            id=int(cultivation_id),
            user_id=current_user.id,
            status='harvested'
        ).first()
        
        if not cultivation:
            flash('Invalid cultivation selected.', 'error')
            return redirect(url_for('selling.add_listing'))
        
        # Get district from land
        district = cultivation.land.district or 'Other'
        
        # Get admin-set price
        price_info = get_crop_price(cultivation.crop_name, district)
        if not price_info:
            flash(f'No price set for {cultivation.crop_name} in {district}. Contact admin.', 'error')
            return render_template('selling/add_listing.html', 
                                   cultivations=harvested_cultivations)
        
        if not quantity:
            flash('Please enter quantity.', 'error')
            return render_template('selling/add_listing.html', 
                                   cultivations=harvested_cultivations)
        
        quantity = float(quantity)
        
        # Validate quantity against actual yield
        if cultivation.actual_yield:
            max_quantity = cultivation.actual_yield * (1 + QUANTITY_TOLERANCE)
            if quantity > max_quantity:
                flash(f'Quantity cannot exceed harvested amount ({cultivation.actual_yield} {cultivation.yield_unit}) plus tolerance.', 'error')
                return render_template('selling/add_listing.html', 
                                       cultivations=harvested_cultivations)
        
        listing = CropListing(
            user_id=current_user.id,
            cultivation_id=cultivation.id,
            crop_name=cultivation.crop_name,
            variety=cultivation.variety,
            quantity=quantity,
            quantity_unit=cultivation.yield_unit,
            price_per_unit=price_info.price_per_unit,  # Auto-set from admin price
            location=current_user.location or district,
            is_organic=False,
            status='available'
        )
        db.session.add(listing)
        
        # Update units sold for the price (round to nearest integer)
        price_info.units_sold += round(quantity)
        
        db.session.commit()
        
        flash('Crop listing added successfully with admin-set pricing!', 'success')
        return redirect(url_for('selling.my_listings'))
    
    return render_template('selling/add_listing.html', 
                           cultivations=harvested_cultivations)


@selling_bp.route('/<int:listing_id>')
def view_listing(listing_id):
    """View listing details."""
    listing = CropListing.query.get_or_404(listing_id)
    return render_template('selling/view_listing.html', listing=listing)


@selling_bp.route('/<int:listing_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing(listing_id):
    """Edit crop listing - only quantity allowed within tolerance."""
    listing = CropListing.query.filter_by(
        id=listing_id, user_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        new_quantity = float(request.form.get('quantity', listing.quantity))
        
        # Check quantity tolerance if linked to cultivation
        if listing.cultivation_id:
            cultivation = Cultivation.query.get(listing.cultivation_id)
            if cultivation and cultivation.actual_yield:
                max_quantity = cultivation.actual_yield * (1 + QUANTITY_TOLERANCE)
                if new_quantity > max_quantity:
                    flash(f'Quantity cannot exceed {max_quantity:.2f} {listing.quantity_unit}', 'error')
                    return render_template('selling/edit_listing.html', listing=listing)
        
        listing.quantity = new_quantity
        # Price cannot be edited by farmer - stays admin-set
        
        db.session.commit()
        flash('Listing updated successfully!', 'success')
        return redirect(url_for('selling.view_listing', listing_id=listing.id))
    
    return render_template('selling/edit_listing.html', listing=listing)


@selling_bp.route('/<int:listing_id>/mark-sold', methods=['POST'])
@login_required
def mark_sold(listing_id):
    """Mark listing as sold."""
    listing = CropListing.query.filter_by(
        id=listing_id, user_id=current_user.id
    ).first_or_404()
    
    listing.status = 'sold'
    db.session.commit()
    flash('Listing marked as sold!', 'success')
    return redirect(url_for('selling.my_listings'))


@selling_bp.route('/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete_listing(listing_id):
    """Delete listing."""
    listing = CropListing.query.filter_by(
        id=listing_id, user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(listing)
    db.session.commit()
    flash('Listing deleted successfully!', 'success')
    return redirect(url_for('selling.my_listings'))
