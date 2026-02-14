"""E-commerce routes for AgriBalance - Seeds, Fertilizers, Machinery."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Product, ProductOrder

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


@ecommerce_bp.route('/order/<int:product_id>', methods=['POST'])
@login_required
def order_product(product_id):
    """Place an order for a product."""
    product = Product.query.get_or_404(product_id)
    
    quantity = request.form.get('quantity', type=int)
    notes = request.form.get('notes', '')
    
    if not quantity or quantity <= 0:
        flash('Please enter a valid quantity.', 'error')
        return redirect(url_for('ecommerce.product_detail', product_id=product_id))
    
    if quantity > product.stock:
        flash(f'Only {product.stock} units available in stock.', 'error')
        return redirect(url_for('ecommerce.product_detail', product_id=product_id))
    
    total_price = product.price * quantity
    
    order = ProductOrder(
        user_id=current_user.id,
        product_id=product_id,
        quantity=quantity,
        total_price=total_price,
        notes=notes
    )
    db.session.add(order)
    db.session.commit()
    
    flash('Order placed successfully! Admin will review your request.', 'success')
    return redirect(url_for('ecommerce.my_orders'))


@ecommerce_bp.route('/my-orders')
@login_required
def my_orders():
    """View user's orders."""
    orders = ProductOrder.query.filter_by(user_id=current_user.id).order_by(
        ProductOrder.created_at.desc()
    ).all()
    
    return render_template('ecommerce/my_orders.html', orders=orders)
