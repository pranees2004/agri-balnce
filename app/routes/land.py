"""Land management routes for AgriBalance."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Land, Cultivation

land_bp = Blueprint('land', __name__)


@land_bp.route('/')
@login_required
def list_lands():
    """List all lands of the user."""
    lands = Land.query.filter_by(user_id=current_user.id).order_by(
        Land.created_at.desc()
    ).all()
    return render_template('land/list.html', lands=lands)


@land_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_land():
    """Add new land."""
    if request.method == 'POST':
        name = request.form.get('name')
        country = request.form.get('country')
        state = request.form.get('state')
        district = request.form.get('district')
        land_size = request.form.get('land_size')
        land_size_unit = request.form.get('land_size_unit', 'acres')
        land_type = request.form.get('land_type')
        soil_type = request.form.get('soil_type')
        climate_type = request.form.get('climate_type')
        water_source = request.form.get('water_source')
        previous_crop = request.form.get('previous_crop')
        notes = request.form.get('notes')
        
        if not name or not country or not land_size:
            flash('Please fill in required fields.', 'error')
            return render_template('land/add.html')
        
        land = Land(
            user_id=current_user.id,
            name=name,
            country=country,
            state=state,
            district=district,
            land_size=float(land_size),
            land_size_unit=land_size_unit,
            land_type=land_type,
            soil_type=soil_type,
            climate_type=climate_type,
            water_source=water_source,
            previous_crop=previous_crop,
            notes=notes
        )
        db.session.add(land)
        db.session.commit()
        
        flash('Land added successfully!', 'success')
        return redirect(url_for('land.list_lands'))
    
    return render_template('land/add.html')


@land_bp.route('/<int:land_id>')
@login_required
def view_land(land_id):
    """View land details."""
    land = Land.query.filter_by(id=land_id, user_id=current_user.id).first_or_404()
    cultivations = Cultivation.query.filter_by(land_id=land_id).order_by(Cultivation.created_at.desc()).all()
    return render_template('land/view.html', land=land, cultivations=cultivations)


@land_bp.route('/<int:land_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_land(land_id):
    """Edit land details."""
    land = Land.query.filter_by(id=land_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        land.name = request.form.get('name', land.name)
        land.country = request.form.get('country', land.country)
        land.state = request.form.get('state', land.state)
        land.district = request.form.get('district', land.district)
        land.land_size = float(request.form.get('land_size', land.land_size))
        land.land_size_unit = request.form.get('land_size_unit', land.land_size_unit)
        land.land_type = request.form.get('land_type', land.land_type)
        land.soil_type = request.form.get('soil_type', land.soil_type)
        land.climate_type = request.form.get('climate_type', land.climate_type)
        land.water_source = request.form.get('water_source', land.water_source)
        land.previous_crop = request.form.get('previous_crop', land.previous_crop)
        land.notes = request.form.get('notes', land.notes)
        
        db.session.commit()
        flash('Land updated successfully!', 'success')
        return redirect(url_for('land.view_land', land_id=land.id))
    
    return render_template('land/edit.html', land=land)


@land_bp.route('/<int:land_id>/delete', methods=['POST'])
@login_required
def delete_land(land_id):
    """Delete land."""
    land = Land.query.filter_by(id=land_id, user_id=current_user.id).first_or_404()
    db.session.delete(land)
    db.session.commit()
    flash('Land deleted successfully!', 'success')
    return redirect(url_for('land.list_lands'))
