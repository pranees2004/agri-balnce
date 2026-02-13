"""E-commerce routes for AgriBalance - Seeds, Fertilizers, Machinery."""
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import Product

ecommerce_bp = Blueprint('ecommerce', __name__)


@ecommerce_bp.route('/')
def products():
    """List all products with optional category filter."""
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    query = Product.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    
    products = query.order_by(Product.name).all()
    
    categories = ['seeds', 'fertilizers', 'pesticides', 'machinery', 'tools']
    
    return render_template(
        'ecommerce/products.html',
        products=products,
        categories=categories,
        selected_category=category,
        search=search
    )


@ecommerce_bp.route('/seeds')
def seeds():
    """View seeds category."""
    products = Product.query.filter_by(category='seeds', is_active=True).all()
    return render_template('ecommerce/category.html', 
                           products=products, category='Seeds')


@ecommerce_bp.route('/fertilizers')
def fertilizers():
    """View fertilizers category."""
    products = Product.query.filter_by(category='fertilizers', is_active=True).all()
    return render_template('ecommerce/category.html', 
                           products=products, category='Fertilizers')


@ecommerce_bp.route('/pesticides')
def pesticides():
    """View pesticides category."""
    products = Product.query.filter_by(category='pesticides', is_active=True).all()
    return render_template('ecommerce/category.html', 
                           products=products, category='Pesticides')


@ecommerce_bp.route('/machinery')
def machinery():
    """View machinery category."""
    products = Product.query.filter_by(category='machinery', is_active=True).all()
    return render_template('ecommerce/category.html', 
                           products=products, category='Machinery')


@ecommerce_bp.route('/tools')
def tools():
    """View tools category."""
    products = Product.query.filter_by(category='tools', is_active=True).all()
    return render_template('ecommerce/category.html', 
                           products=products, category='Tools')


@ecommerce_bp.route('/<int:product_id>')
def product_detail(product_id):
    """View product details."""
    product = Product.query.get_or_404(product_id)
    related_products = Product.query.filter_by(
        category=product.category,
        is_active=True
    ).filter(Product.id != product_id).limit(4).all()
    
    return render_template('ecommerce/product_detail.html', 
                           product=product, related_products=related_products)
