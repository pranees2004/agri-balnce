"""Cultivation routes with AI advisory for AgriBalance."""
import json
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Land, Cultivation, CropPrice, RegionLimit

cultivation_bp = Blueprint('cultivation', __name__)


def get_crop_price(crop_name, district):
    """Get the current price for a crop in a specific district."""
    price = CropPrice.query.filter_by(
        crop_name=crop_name,
        district=district,
        is_active=True
    ).first()
    return price


def check_region_limits(crop_name, district, area_needed):
    """Check if cultivation is allowed based on admin-defined limits."""
    limit = RegionLimit.query.filter_by(
        crop_name=crop_name,
        district=district,
        is_active=True
    ).first()
    
    if not limit:
        return True, None  # No limits set, allow cultivation
    
    remaining_area = limit.max_area - limit.current_area_used
    if area_needed > remaining_area:
        return False, f"Only {remaining_area} acres available for {crop_name} in {district}"
    
    if limit.max_cultivation_count > 0:
        if limit.current_cultivation_count >= limit.max_cultivation_count:
            return False, f"Maximum farmers ({limit.max_cultivation_count}) already cultivating {crop_name} in {district}"
    
    return True, None


def get_ai_recommendations(land, selected_crop=None):
    """
    Generate AI-based advisory suggestions.
    Respects admin-defined limits and rules.
    """
    recommendations = {
        'suitable_crops': [],
        'cultivation_time': '',
        'management_steps': [],
        'nutrient_guidance': [],
        'price_trends': [],
        'land_usage': [],
        'admin_limits': []
    }
    
    # Crop suggestions based on soil type
    soil_crops = {
        'clay': ['Rice', 'Wheat', 'Cotton', 'Sugarcane'],
        'loam': ['Vegetables', 'Fruits', 'Wheat', 'Corn', 'Pulses'],
        'sandy': ['Groundnut', 'Carrot', 'Potato', 'Watermelon'],
        'black': ['Cotton', 'Soybean', 'Sunflower', 'Wheat'],
        'red': ['Millets', 'Groundnut', 'Tobacco', 'Pulses'],
        'alluvial': ['Rice', 'Wheat', 'Sugarcane', 'Jute', 'Maize']
    }
    
    soil_type = (land.soil_type or '').lower()
    recommendations['suitable_crops'] = soil_crops.get(soil_type, 
        ['Wheat', 'Rice', 'Vegetables', 'Pulses'])
    
    # Climate-based timing
    climate_timing = {
        'tropical': 'Year-round cultivation possible. Best: June-September (Kharif), October-February (Rabi)',
        'subtropical': 'Best planting: March-April (Summer), October-November (Winter)',
        'temperate': 'Spring planting (March-May), Autumn harvest (September-November)',
        'arid': 'Monsoon season recommended. Use drought-resistant varieties.'
    }
    recommendations['cultivation_time'] = climate_timing.get(
        (land.climate_type or '').lower(),
        'Consult local agricultural office for best planting times.'
    )
    
    # Management steps (generic)
    recommendations['management_steps'] = [
        'Prepare land 2-3 weeks before planting - plowing and leveling',
        'Test soil and apply base fertilizers as recommended',
        'Select quality seeds from certified sources',
        'Maintain proper spacing for optimal growth',
        'Regular irrigation based on crop water requirements',
        'Monitor for pests and diseases weekly',
        'Apply fertilizers at key growth stages',
        'Harvest at optimal maturity for best quality'
    ]
    
    # Nutrient guidance based on soil type
    nutrient_guide = {
        'clay': [
            'Add organic matter to improve drainage',
            'Apply gypsum to improve soil structure',
            'Nitrogen: 80-120 kg/hectare in split doses',
            'Phosphorus: Apply before planting (40-60 kg/hectare)'
        ],
        'sandy': [
            'Add organic compost to improve water retention',
            'Apply nutrients in smaller, frequent doses',
            'Use slow-release fertilizers',
            'Maintain mulching to prevent nutrient leaching'
        ],
        'loam': [
            'Maintain organic matter with crop rotation',
            'Balanced NPK application recommended',
            'Green manuring between seasons',
            'Regular soil testing every season'
        ]
    }
    recommendations['nutrient_guidance'] = nutrient_guide.get(soil_type, [
        'Get soil tested at nearest agricultural lab',
        'Apply balanced NPK fertilizers',
        'Use organic manure along with chemical fertilizers',
        'Consider micronutrient supplements'
    ])
    
    # Price trends and land usage
    recommendations['price_trends'] = [
        'Advisory: Check local mandi prices before deciding crops',
        'Consider contract farming for price stability',
        'Diversify crops to reduce market risk',
        'Store produce if prices are low at harvest time'
    ]
    
    recommendations['land_usage'] = [
        f'Land size: {land.land_size} {land.land_size_unit}',
        'Suggestion: Allocate 70% to main crop, 30% to secondary crop',
        'Leave field boundaries for beneficial insects',
        'Consider intercropping for better land utilization'
    ]
    
    # Add admin-defined limits info
    district = land.district or 'Other'
    limits = RegionLimit.query.filter_by(district=district, is_active=True).all()
    if limits:
        for limit in limits:
            remaining = limit.max_area - limit.current_area_used
            recommendations['admin_limits'].append(
                f'{limit.crop_name}: {remaining:.1f} acres available (max {limit.max_area} acres)'
            )
    
    return recommendations


@cultivation_bp.route('/')
@login_required
def list_cultivations():
    """List all cultivations of the user."""
    cultivations = Cultivation.query.filter_by(user_id=current_user.id).order_by(
        Cultivation.created_at.desc()
    ).all()
    return render_template('cultivation/list.html', cultivations=cultivations)


@cultivation_bp.route('/active')
@login_required
def active_cultivations():
    """View active cultivations with crop details and area-wise daily prices."""
    cultivations = Cultivation.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).order_by(Cultivation.expected_harvest_date).all()
    
    # Get prices for each cultivation
    cultivation_data = []
    for cult in cultivations:
        district = cult.land.district or 'Other'
        price_info = get_crop_price(cult.crop_name, district)
        
        # Calculate estimated area value (area * price per unit)
        # This represents the potential value based on area cultivation
        area_value = 0
        if price_info and cult.area_used:
            area_value = cult.area_used * price_info.price_per_unit
        
        cultivation_data.append({
            'cultivation': cult,
            'price_per_unit': price_info.price_per_unit if price_info else 0,
            'price_unit': price_info.unit if price_info else 'kg',
            'area_value': area_value,
            'district': district
        })
    
    return render_template('cultivation/active.html', cultivation_data=cultivation_data)


@cultivation_bp.route('/start', methods=['GET', 'POST'])
@login_required
def start_cultivation():
    """Start new cultivation with AI advisory."""
    lands = Land.query.filter_by(user_id=current_user.id).all()
    
    if not lands:
        flash('Please add a land first before starting cultivation.', 'warning')
        return redirect(url_for('land.add_land'))
    
    selected_land = None
    recommendations = None
    
    if request.method == 'POST':
        land_id = request.form.get('land_id')
        crop_name = request.form.get('crop_name')
        variety = request.form.get('variety')
        planting_date = request.form.get('planting_date')
        expected_harvest_date = request.form.get('expected_harvest_date')
        notes = request.form.get('notes')
        
        if 'get_recommendations' in request.form:
            # Just get recommendations without saving
            selected_land = Land.query.filter_by(
                id=land_id, user_id=current_user.id
            ).first()
            if selected_land:
                recommendations = get_ai_recommendations(selected_land, crop_name)
            return render_template(
                'cultivation/start.html',
                lands=lands,
                selected_land=selected_land,
                recommendations=recommendations
            )
        
        if 'save_cultivation' in request.form:
            if not land_id or not crop_name:
                flash('Please select a land and enter crop name.', 'error')
                return render_template('cultivation/start.html', lands=lands)
            
            selected_land = Land.query.filter_by(
                id=land_id, user_id=current_user.id
            ).first()
            
            if selected_land:
                recommendations = get_ai_recommendations(selected_land, crop_name)
                
                cultivation = Cultivation(
                    user_id=current_user.id,
                    land_id=int(land_id),
                    crop_name=crop_name,
                    variety=variety,
                    planting_date=datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else None,
                    expected_harvest_date=datetime.strptime(expected_harvest_date, '%Y-%m-%d').date() if expected_harvest_date else None,
                    status='planned',
                    ai_recommendations=json.dumps(recommendations),
                    notes=notes
                )
                db.session.add(cultivation)
                db.session.commit()
                
                flash('Cultivation started successfully!', 'success')
                return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation.id))
    
    return render_template(
        'cultivation/start.html',
        lands=lands,
        selected_land=selected_land,
        recommendations=recommendations
    )


@cultivation_bp.route('/<int:cultivation_id>')
@login_required
def view_cultivation(cultivation_id):
    """View cultivation details with AI recommendations."""
    cultivation = Cultivation.query.filter_by(
        id=cultivation_id, user_id=current_user.id
    ).first_or_404()
    
    recommendations = None
    if cultivation.ai_recommendations:
        try:
            recommendations = json.loads(cultivation.ai_recommendations)
        except json.JSONDecodeError:
            recommendations = None
    
    return render_template(
        'cultivation/view.html',
        cultivation=cultivation,
        recommendations=recommendations
    )


@cultivation_bp.route('/<int:cultivation_id>/update-status', methods=['POST'])
@login_required
def update_status(cultivation_id):
    """Update cultivation status."""
    cultivation = Cultivation.query.filter_by(
        id=cultivation_id, user_id=current_user.id
    ).first_or_404()
    
    new_status = request.form.get('status')
    if new_status in ['planned', 'active', 'harvested', 'failed']:
        cultivation.status = new_status
        
        if new_status == 'harvested':
            cultivation.actual_harvest_date = datetime.utcnow().date()
            actual_yield = request.form.get('actual_yield')
            if actual_yield:
                cultivation.actual_yield = float(actual_yield)
        
        db.session.commit()
        flash(f'Status updated to {new_status}!', 'success')
    
    return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation_id))


@cultivation_bp.route('/history')
@login_required
def cultivation_history():
    """View cultivation history."""
    cultivations = Cultivation.query.filter_by(user_id=current_user.id).filter(
        Cultivation.status.in_(['harvested', 'failed'])
    ).order_by(Cultivation.actual_harvest_date.desc()).all()
    
    return render_template('cultivation/history.html', cultivations=cultivations)
