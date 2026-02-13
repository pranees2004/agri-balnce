"""Cultivation routes with AI advisory for AgriBalance."""
import json
import uuid
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Land, Cultivation, CropPrice, RegionLimit, AdminQuota, CropMaster, Notification

cultivation_bp = Blueprint('cultivation', __name__)

# Tolerance for quantity variations (5% to account for measurement inaccuracies)
HARVEST_QUANTITY_TOLERANCE = 0.05

# Yield estimation factors (based on agricultural research averages)
# Keys use lowercase to match normalized input
SOIL_QUALITY_FACTORS = {
    'loam': 1.1,        # Better drainage and nutrient retention
    'alluvial': 1.1,    # Fertile river-deposited soil
    'sandy': 0.9,       # Lower water and nutrient retention
    'red': 1.0,         # Standard baseline
    'black': 1.0,       # Standard baseline
    'clay': 1.0         # Standard baseline
}

WATER_AVAILABILITY_FACTORS = {
    'borewell': 1.05,   # Reliable water supply
    'canal': 1.05,      # Assured irrigation
    'rain-fed': 0.85,   # Dependent on rainfall
    'rain': 0.85        # Rain-fed alternative key
}


def get_crop_price(crop_name, district, harvest_date=None):
    """Get the current price for a crop in a specific district.
    
    If harvest_date is provided, returns price valid for that date period.
    Otherwise returns any active price for the crop/district.
    """
    query = CropPrice.query.filter_by(
        crop_name=crop_name,
        district=district,
        is_active=True
    )
    
    # If harvest date provided, filter by date period
    if harvest_date:
        if isinstance(harvest_date, str):
            try:
                harvest_date = datetime.strptime(harvest_date, '%Y-%m-%d').date()
            except ValueError:
                # If date format is invalid, return without date filtering
                # This allows the function to gracefully handle invalid dates
                # and return any active price for the crop/district
                pass
            except Exception:
                # Handle any other parsing errors
                pass
        
        # Only apply date filtering if harvest_date was successfully parsed
        if isinstance(harvest_date, date):
            query = query.filter(
                db.or_(
                    CropPrice.valid_from.is_(None),
                    CropPrice.valid_from <= harvest_date
                )
            ).filter(
                db.or_(
                    CropPrice.valid_to.is_(None),
                    CropPrice.valid_to >= harvest_date
                )
            )
    
    price = query.first()
    return price


def generate_cultivation_approval_id():
    """Generate unique cultivation approval ID."""
    return f"CA-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def find_matching_quota(land, crop_name):
    """Find matching quota for given land and crop."""
    # Try to find quota matching location (from most specific to least specific)
    quota = None
    
    # Try village level first
    if land.village:
        quota = AdminQuota.query.filter_by(
            crop_name=crop_name,
            village=land.village,
            is_active=True
        ).first()
        if quota:
            return quota
    
    # Try taluk level
    if land.taluk:
        quota = AdminQuota.query.filter_by(
            crop_name=crop_name,
            taluk=land.taluk,
            village=None,
            is_active=True
        ).first()
        if quota:
            return quota
    
    # Try district level
    if land.district:
        quota = AdminQuota.query.filter_by(
            crop_name=crop_name,
            district=land.district,
            taluk=None,
            village=None,
            is_active=True
        ).first()
        if quota:
            return quota
    
    # Try state level
    if land.state:
        quota = AdminQuota.query.filter_by(
            crop_name=crop_name,
            state=land.state,
            district=None,
            taluk=None,
            village=None,
            is_active=True
        ).first()
        if quota:
            return quota
    
    # Try country level
    quota = AdminQuota.query.filter_by(
        crop_name=crop_name,
        country=land.country,
        state=None,
        district=None,
        taluk=None,
        village=None,
        is_active=True
    ).first()
    
    return quota


def check_admin_quota(land, crop_name, area_needed):
    """Check if cultivation is allowed based on admin-defined quotas (new system)."""
    quota = find_matching_quota(land, crop_name)
    
    if not quota:
        # Check old RegionLimit system for backward compatibility
        return check_region_limits(crop_name, land.district or 'Other', area_needed)
    
    # Check if quota is available
    is_available, message = quota.is_quota_available(area_needed, current_user.id)
    
    if not is_available:
        return False, message, None
    
    return True, "Quota available", quota


def check_region_limits(crop_name, district, area_needed):
    """Check if cultivation is allowed based on admin-defined limits (legacy system)."""
    limit = RegionLimit.query.filter_by(
        crop_name=crop_name,
        district=district,
        is_active=True
    ).first()
    
    if not limit:
        return True, None, None  # No limits set, allow cultivation
    
    remaining_area = limit.max_area - limit.current_area_used
    if area_needed > remaining_area:
        return False, f"Only {remaining_area} acres available for {crop_name} in {district}", None
    
    if limit.max_cultivation_count > 0:
        if limit.current_cultivation_count >= limit.max_cultivation_count:
            return False, f"Maximum farmers ({limit.max_cultivation_count}) already cultivating {crop_name} in {district}", None
    
    return True, None, None


def get_ai_recommendations(land, selected_crop=None, requested_area=None):
    """
    Generate AI-based advisory suggestions.
    Respects admin-defined limits and rules.
    AI never overrides admin-set limits - admin rules have highest priority.
    """
    recommendations = {
        'suitable_crops': [],
        'primary_crop': None,
        'alternative_crops': [],
        'cultivation_time': '',
        'management_steps': [],
        'nutrient_guidance': [],
        'fertilizer_plan': {},
        'irrigation_schedule': [],
        'pest_prevention': [],
        'mixed_cropping': [],
        'price_trends': [],
        'land_usage': [],
        'admin_limits': [],
        'quota_status': {},
        'expected_yield': None,
        'expected_harvest_window': '',
        'risk_assessment': {}
    }
    
    # Check crop master database
    if selected_crop:
        crop_master = CropMaster.query.filter_by(crop_name=selected_crop, is_active=True).first()
        if crop_master:
            recommendations['crop_master_info'] = {
                'avg_yield_per_acre': crop_master.avg_yield_per_acre,
                'growth_duration_days': crop_master.growth_duration_days,
                'water_requirement': crop_master.water_requirement,
                'season': crop_master.season
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
    suitable_crops = soil_crops.get(soil_type, ['Wheat', 'Rice', 'Vegetables', 'Pulses'])
    
    # Check quota availability for suitable crops
    crops_with_quota = []
    for crop in suitable_crops:
        quota = find_matching_quota(land, crop)
        if quota and quota.remaining_area() > 0:
            crops_with_quota.append({
                'crop': crop,
                'available_area': quota.remaining_area(),
                'quota_utilization': (quota.allocated_area / quota.total_allowed_area * 100) if quota.total_allowed_area > 0 else 0
            })
    
    # Sort by availability
    crops_with_quota.sort(key=lambda x: x['available_area'], reverse=True)
    recommendations['suitable_crops'] = [c['crop'] for c in crops_with_quota]
    
    if crops_with_quota:
        recommendations['primary_crop'] = crops_with_quota[0]['crop']
        recommendations['alternative_crops'] = [c['crop'] for c in crops_with_quota[1:4]]
    
    # Climate-based timing
    climate_timing = {
        'tropical': 'Year-round cultivation possible. Best: June-September (Kharif), October-February (Rabi)',
        'subtropical': 'Best planting: March-April (Summer), October-November (Winter)',
        'temperate': 'Spring planting (March-May), Autumn harvest (September-November)',
        'arid': 'Monsoon season recommended. Use drought-resistant varieties.',
        'semi-arid': 'Kharif season (June-September) with monsoon. Consider drought-resistant varieties.',
        'humid': 'Year-round cultivation with proper drainage. Avoid waterlogging in monsoon.'
    }
    recommendations['cultivation_time'] = climate_timing.get(
        (land.climate_type or '').lower(),
        'Consult local agricultural office for best planting times.'
    )
    
    # Management steps (comprehensive)
    recommendations['management_steps'] = [
        '1. Land Preparation (2-3 weeks before): Deep plowing and leveling',
        '2. Soil Testing: Get soil tested at nearest Krishi Vigyan Kendra',
        '3. Seed Selection: Purchase certified seeds from authorized dealers',
        '4. Base Fertilizer Application: Apply organic manure and basal dose',
        '5. Sowing/Planting: Maintain recommended spacing for variety',
        '6. Irrigation Management: Follow crop-specific water requirements',
        '7. Weed Control: Manual or herbicide application at critical stages',
        '8. Pest & Disease Monitoring: Weekly inspection and timely intervention',
        '9. Nutrient Management: Top dressing at growth stages',
        '10. Harvest: At optimal maturity for maximum yield and quality'
    ]
    
    # Fertilizer plan with NPK ratios
    recommendations['fertilizer_plan'] = {
        'basal_dose': {
            'timing': 'At the time of sowing/planting',
            'nitrogen': '20-30% of total N requirement',
            'phosphorus': '100% of P requirement',
            'potassium': '50% of K requirement',
            'organic': 'Apply 5-10 tonnes FYM per acre'
        },
        'top_dressing': [
            {
                'stage': 'Vegetative stage (3-4 weeks)',
                'nitrogen': '30-40% of total N',
                'potassium': '25% of K requirement'
            },
            {
                'stage': 'Flowering/Grain filling (6-8 weeks)',
                'nitrogen': '30-40% of total N',
                'potassium': '25% of K requirement'
            }
        ],
        'micronutrients': 'Zinc, Boron as per soil test recommendations'
    }
    
    # Irrigation schedule
    water_source_schedule = {
        'rain-fed': [
            'Pre-sowing irrigation if monsoon is delayed',
            'Supplemental irrigation during dry spells (7-10 days interval)',
            'Critical stages: Flowering and grain filling - ensure adequate moisture'
        ],
        'borewell': [
            'Drip irrigation recommended for water efficiency',
            'Irrigation interval: 3-5 days depending on crop and season',
            'Critical stages: Apply 50-60mm at flowering and grain development',
            'Use mulching to reduce water loss'
        ],
        'canal': [
            'Irrigation based on canal release schedule',
            'Maintain field water level as per crop requirement',
            'Ensure proper drainage to prevent waterlogging',
            'Coordinate with water user association'
        ],
        'tank': [
            'Plan cultivation based on tank storage levels',
            'Adopt water-saving techniques like SRI for rice',
            'Alternate wetting and drying for efficient water use',
            'Monitor tank levels regularly'
        ]
    }
    water_source = (land.water_source or '').lower()
    recommendations['irrigation_schedule'] = water_source_schedule.get(
        water_source,
        ['Ensure adequate water availability throughout crop growth', 'Irrigate at critical growth stages']
    )
    
    # Pest prevention guide
    recommendations['pest_prevention'] = [
        'Preventive Measures:',
        '- Use disease-free certified seeds',
        '- Maintain field sanitation and remove crop residues',
        '- Practice crop rotation to break pest cycles',
        '- Install pheromone traps for monitoring',
        'Monitoring:',
        '- Inspect crops weekly for early detection',
        '- Check underside of leaves for eggs/larvae',
        '- Identify beneficial insects (ladybugs, spiders)',
        'Control Measures:',
        '- Use neem-based organic pesticides for minor infestations',
        '- Apply recommended chemical pesticides only when needed',
        '- Follow safety precautions and waiting periods',
        '- Consult agricultural officer for disease identification'
    ]
    
    # Mixed cropping options
    intercrop_combinations = {
        'cotton': ['Green gram', 'Black gram', 'Soybean (1:2 ratio)'],
        'sugarcane': ['Onion', 'Coriander', 'Potato in inter-row space'],
        'maize': ['Beans', 'Pumpkin (3:1 ratio)', 'Cowpea'],
        'coconut': ['Banana', 'Turmeric', 'Ginger', 'Pineapple under coconut canopy']
    }
    
    if selected_crop and selected_crop.lower() in intercrop_combinations:
        recommendations['mixed_cropping'] = intercrop_combinations[selected_crop.lower()]
    else:
        recommendations['mixed_cropping'] = [
            'Legumes (pulses) can be intercropped to improve soil nitrogen',
            'Short duration vegetables in field borders',
            'Consider border crops for additional income'
        ]
    
    # Expected yield estimation
    if selected_crop and requested_area:
        crop_master = CropMaster.query.filter_by(crop_name=selected_crop, is_active=True).first()
        if crop_master and crop_master.avg_yield_per_acre:
            # Apply soil and water adjustments using documented factors
            soil_factor = SOIL_QUALITY_FACTORS.get(soil_type, 1.0)
            
            # Extract base water source type for factor lookup
            water_factor = 1.0
            if land.water_source:
                water_source_lower = land.water_source.lower()
                for key, factor in WATER_AVAILABILITY_FACTORS.items():
                    if key in water_source_lower:
                        water_factor = factor
                        break
            
            estimated_yield = crop_master.avg_yield_per_acre * requested_area * soil_factor * water_factor
            recommendations['expected_yield'] = {
                'quantity': round(estimated_yield, 2),
                'unit': crop_master.yield_unit,
                'per_acre': round(crop_master.avg_yield_per_acre * soil_factor * water_factor, 2)
            }
            
            # Expected harvest window based on planting date or current date
            if crop_master.growth_duration_days:
                # Use current date as projection basis
                start_date = datetime.utcnow()
                end_date = start_date + timedelta(days=crop_master.growth_duration_days)
                recommendations['expected_harvest_window'] = f"{start_date.strftime('%B %Y')} - {end_date.strftime('%B %Y')}"
                recommendations['growth_info'] = f"Projected {crop_master.growth_duration_days} days from cultivation start"
    
    # Risk probability assessment
    risk_factors = []
    risk_score = 0
    
    # Water availability risk
    if land.water_source and 'rain-fed' in land.water_source.lower():
        risk_factors.append('Rain-fed agriculture has monsoon dependency risk')
        risk_score += 2
    
    # Soil suitability
    if selected_crop:
        # Normalize for case-insensitive comparison
        soil_suitable = (
            soil_type in SOIL_QUALITY_FACTORS or 
            selected_crop in soil_crops.get(soil_type, [])
        )
        if not soil_suitable:
            risk_factors.append('Soil type may not be ideal for selected crop')
            risk_score += 1
    
    # Market factors
    if selected_crop:
        # Check if quota is nearly full (high competition risk)
        quota = find_matching_quota(land, selected_crop)
        if quota:
            utilization = (quota.allocated_area / quota.total_allowed_area * 100) if quota.total_allowed_area > 0 else 0
            if utilization > 80:
                risk_factors.append('High quota utilization - market may be saturated')
                risk_score += 2
    
    # Determine risk level
    if risk_score <= 1:
        risk_level = 'Low'
        risk_color = 'green'
    elif risk_score <= 3:
        risk_level = 'Medium'
        risk_color = 'yellow'
    else:
        risk_level = 'High'
        risk_color = 'red'
    
    recommendations['risk_assessment'] = {
        'level': risk_level,
        'color': risk_color,
        'factors': risk_factors if risk_factors else ['No significant risk factors identified'],
        'score': risk_score
    }
    
    # Price trends and land usage
    recommendations['price_trends'] = [
        'Advisory: Check local mandi prices before deciding crops',
        'Consider contract farming for price stability',
        'Diversify crops to reduce market risk',
        'Store produce if prices are low at harvest time',
        'Join farmer producer organizations for better bargaining'
    ]
    
    # Land usage optimization
    area_suggestion = requested_area or land.land_size
    recommendations['land_usage'] = [
        f'Total land size: {land.land_size} {land.land_size_unit}',
        f'Suggested cultivation area: {area_suggestion * 0.9:.2f} {land.land_size_unit} (90% of available)',
        'Reserve 10% for field bunds and access paths',
        'Consider intercropping for better land utilization',
        'Maintain buffer zones for beneficial insects',
        'Plan crop rotation for next season'
    ]
    
    # Add admin-defined quota information (Admin rules have highest priority)
    district = land.district or 'Other'
    
    # Check new quota system
    if selected_crop:
        quota = find_matching_quota(land, selected_crop)
        if quota:
            remaining = quota.remaining_area()
            utilization = (quota.allocated_area / quota.total_allowed_area * 100) if quota.total_allowed_area > 0 else 0
            recommendations['quota_status'] = {
                'available': remaining,
                'total': quota.total_allowed_area,
                'utilization': round(utilization, 1),
                'max_per_farmer': quota.max_per_farmer
            }
            recommendations['admin_limits'].append(
                f'✓ {selected_crop}: {remaining:.1f} {quota.area_unit} available out of {quota.total_allowed_area} {quota.area_unit} ({utilization:.1f}% used)'
            )
            if quota.max_per_farmer:
                recommendations['admin_limits'].append(
                    f'  Max per farmer: {quota.max_per_farmer} {quota.area_unit}'
                )
            if quota.harvest_season_start and quota.harvest_season_end:
                recommendations['admin_limits'].append(
                    f'  Harvest season: {quota.harvest_season_start.strftime("%b %Y")} - {quota.harvest_season_end.strftime("%b %Y")}'
                )
    
    # Also check old region limits for backward compatibility
    limits = RegionLimit.query.filter_by(district=district, is_active=True).all()
    if limits:
        for limit in limits:
            remaining = limit.max_area - limit.current_area_used
            utilization = (limit.current_area_used / limit.max_area * 100) if limit.max_area > 0 else 0
            recommendations['admin_limits'].append(
                f'{limit.crop_name}: {remaining:.1f} acres available (max {limit.max_area} acres, {utilization:.1f}% used)'
            )
    
    if not recommendations['admin_limits']:
        recommendations['admin_limits'].append('No specific quota restrictions for this location')
    
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
    """Start new cultivation with quota enforcement and admin-controlled pricing."""
    lands = Land.query.filter_by(user_id=current_user.id).all()
    
    if not lands:
        flash('Please add a land first before starting cultivation.', 'warning')
        return redirect(url_for('land.add_land'))
    
    selected_land = None
    quota_check_result = None
    
    if request.method == 'POST':
        land_id = request.form.get('land_id')
        crop_name = request.form.get('crop_name')
        variety = request.form.get('variety')
        area_to_use = request.form.get('area_to_use')
        planting_date = request.form.get('planting_date')
        expected_harvest_date = request.form.get('expected_harvest_date')
        notes = request.form.get('notes')
        
        if 'save_cultivation' in request.form:
            if not land_id or not crop_name or not area_to_use:
                flash('Please select a land, enter crop name, and specify area to use.', 'error')
                return render_template('cultivation/start.html', lands=lands)
            
            selected_land = Land.query.filter_by(
                id=land_id, user_id=current_user.id
            ).first()
            
            if not selected_land:
                flash('Invalid land selected.', 'error')
                return render_template('cultivation/start.html', lands=lands)
            
            area_requested = float(area_to_use)
            
            # Validate area
            if area_requested > selected_land.land_size:
                flash(f'Cultivation area cannot exceed land size ({selected_land.land_size} {selected_land.land_size_unit}).', 'error')
                return render_template('cultivation/start.html', lands=lands)
            
            # Check quota enforcement (CRITICAL - Admin rules have highest priority)
            quota_allowed, quota_message, quota_obj = check_admin_quota(
                selected_land, crop_name, area_requested
            )
            
            if not quota_allowed:
                flash(f'Cultivation blocked by admin quota: {quota_message}', 'error')
                
                quota_check_result = {
                    'allowed': False,
                    'message': quota_message,
                    'quota': quota_obj
                }
                
                return render_template(
                    'cultivation/start.html',
                    lands=lands,
                    selected_land=selected_land,
                    quota_check=quota_check_result
                )
            
            # Generate cultivation approval ID
            approval_id = generate_cultivation_approval_id()
            
            # Get AI recommendations internally for yield estimation
            # Note: Recommendations are not displayed to user but are used for:
            # 1. Calculating estimated yield and max sale quantity
            # 2. Storing in database for admin reference and future viewing
            recommendations = get_ai_recommendations(selected_land, crop_name, area_requested)
            
            # Calculate estimated yield and max allowed sale quantity
            estimated_yield = None
            max_sale_qty = None
            if recommendations.get('expected_yield'):
                estimated_yield = recommendations['expected_yield']['quantity']
                # Allow tolerance for measurement variations (defined constant)
                max_sale_qty = estimated_yield * (1 + HARVEST_QUANTITY_TOLERANCE)
            
            # Create cultivation record with quota reservation
            try:
                cultivation = Cultivation(
                    cultivation_approval_id=approval_id,
                    user_id=current_user.id,
                    land_id=int(land_id),
                    quota_id=quota_obj.id if quota_obj else None,
                    crop_name=crop_name,
                    variety=variety,
                    area_used=area_requested,
                    planting_date=datetime.strptime(planting_date, '%Y-%m-%d').date() if planting_date else None,
                    expected_harvest_date=datetime.strptime(expected_harvest_date, '%Y-%m-%d').date() if expected_harvest_date else None,
                    status='planned',
                    estimated_yield=estimated_yield,
                    max_allowed_sale_quantity=max_sale_qty,
                    yield_unit='kg',
                    ai_recommendations=json.dumps(recommendations),
                    notes=notes
                )
                db.session.add(cultivation)
                
                # Reserve area from quota (atomic operation)
                if quota_obj:
                    quota_obj.allocated_area += area_requested
                    quota_obj.allocated_farmer_count += 1
                    quota_obj.updated_at = datetime.utcnow()
                
                # Update old RegionLimit if no quota (backward compatibility)
                elif selected_land.district:
                    region_limit = RegionLimit.query.filter_by(
                        crop_name=crop_name,
                        district=selected_land.district,
                        is_active=True
                    ).first()
                    if region_limit:
                        region_limit.current_area_used += area_requested
                        region_limit.current_cultivation_count += 1
                
                db.session.commit()
                
                flash(f'Cultivation started successfully! Approval ID: {approval_id}', 'success')
                return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation.id))
            
            except Exception as e:
                db.session.rollback()
                flash(f'Error starting cultivation: {str(e)}', 'error')
                return render_template('cultivation/start.html', lands=lands)
    
    # Query available quotas based on user's land locations
    land_districts = set(land.district for land in lands if land.district)
    land_states = set(land.state for land in lands if land.state)
    land_countries = set(land.country for land in lands if land.country)

    quota_filters = []
    if land_districts:
        quota_filters.append(AdminQuota.district.in_(land_districts))
    if land_states:
        quota_filters.append(AdminQuota.state.in_(land_states))
    if land_countries:
        quota_filters.append(AdminQuota.country.in_(land_countries))

    if quota_filters:
        available_quotas = AdminQuota.query.filter(
            AdminQuota.is_active == True,
            db.or_(*quota_filters)
        ).all()
    else:
        available_quotas = []

    return render_template(
        'cultivation/start.html',
        lands=lands,
        selected_land=selected_land,
        quota_check=quota_check_result,
        available_quotas=available_quotas
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


@cultivation_bp.route('/<int:cultivation_id>/submit-harvest', methods=['GET', 'POST'])
@login_required
def submit_harvest(cultivation_id):
    """Submit harvest for sale with admin-controlled pricing."""
    from app.models import HarvestSale, Notification
    
    cultivation = Cultivation.query.filter_by(
        id=cultivation_id, user_id=current_user.id
    ).first_or_404()
    
    if cultivation.status != 'harvested':
        flash('Only harvested cultivations can be submitted for sale.', 'warning')
        return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation_id))
    
    # Check if already submitted
    existing_sale = HarvestSale.query.filter_by(cultivation_id=cultivation_id).first()
    if existing_sale:
        flash('Harvest already submitted for this cultivation. Contact admin to modify.', 'info')
        return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation_id))
    
    # Get admin-set price for this crop, district, and harvest date
    district = cultivation.land.district or 'Other'
    harvest_date = cultivation.actual_harvest_date or date.today()
    admin_price = get_crop_price(cultivation.crop_name, district, harvest_date)
    
    if request.method == 'POST':
        actual_yield = request.form.get('actual_yield')
        selling_quantity = request.form.get('selling_quantity')
        contact_number = request.form.get('contact_number')
        photos = request.form.get('photos')  # JSON or comma-separated URLs
        
        if not actual_yield or not selling_quantity:
            flash('Please provide actual yield and selling quantity.', 'error')
            return render_template('cultivation/submit_harvest.html', 
                                   cultivation=cultivation,
                                   admin_price=admin_price)
        
        actual_yield = float(actual_yield)
        selling_quantity = float(selling_quantity)
        
        # Validate selling quantity against cultivation limits
        if cultivation.max_allowed_sale_quantity:
            if selling_quantity > cultivation.max_allowed_sale_quantity:
                flash(f'Selling quantity cannot exceed {cultivation.max_allowed_sale_quantity} {cultivation.yield_unit} (based on allocated area).', 'error')
                return render_template('cultivation/submit_harvest.html', 
                                       cultivation=cultivation,
                                       admin_price=admin_price)
        
        # Validate selling quantity against actual yield (with tolerance)
        if selling_quantity > actual_yield * (1 + HARVEST_QUANTITY_TOLERANCE):
            flash(f'Selling quantity cannot exceed actual yield ({actual_yield} {cultivation.yield_unit}) plus {HARVEST_QUANTITY_TOLERANCE*100}% tolerance.', 'error')
            return render_template('cultivation/submit_harvest.html', 
                                   cultivation=cultivation,
                                   admin_price=admin_price)
        
        # Use admin-set price if available, otherwise allow farmer expectation
        selling_price = None
        if admin_price:
            selling_price = admin_price.price_per_unit
        else:
            # Allow farmer to set expectation if no admin price available
            selling_price_input = request.form.get('selling_price_expectation')
            if selling_price_input:
                selling_price = float(selling_price_input)
        
        # Create harvest sale submission with admin price
        harvest_sale = HarvestSale(
            cultivation_id=cultivation_id,
            user_id=current_user.id,
            actual_yield_quantity=actual_yield,
            yield_unit=cultivation.yield_unit,
            selling_quantity=selling_quantity,
            selling_price_expectation=selling_price,
            contact_number=contact_number or current_user.mobile,
            photos=photos,
            status='pending'
        )
        db.session.add(harvest_sale)
        
        # Update cultivation actual yield
        cultivation.actual_yield = actual_yield
        
        # Create notifications for all admins
        from app.models import User
        admins = User.query.filter_by(is_admin=True).all()
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                notification_type='harvest_submitted',
                title='New Harvest Sale Submission',
                message=f'Farmer {current_user.name} submitted harvest for {cultivation.crop_name}. Approval ID: {cultivation.cultivation_approval_id}',
                related_cultivation_id=cultivation_id,
                related_harvest_sale_id=harvest_sale.id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        flash('Harvest submitted for admin approval!', 'success')
        return redirect(url_for('cultivation.view_cultivation', cultivation_id=cultivation_id))
    
    return render_template('cultivation/submit_harvest.html', 
                           cultivation=cultivation,
                           admin_price=admin_price)
