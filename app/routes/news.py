"""News and Government Schemes routes for AgriBalance."""
from flask import Blueprint, render_template, request
from app.models import NewsArticle

news_bp = Blueprint('news', __name__)


@news_bp.route('/')
def news_list():
    """List all news and schemes."""
    category = request.args.get('category', '')
    
    query = NewsArticle.query.filter_by(is_published=True)
    
    if category:
        query = query.filter_by(category=category)
    
    # Featured first, then by date
    articles = query.order_by(
        NewsArticle.is_featured.desc(),
        NewsArticle.published_at.desc()
    ).all()
    
    categories = ['news', 'scheme', 'announcement', 'tip']
    
    return render_template(
        'news/list.html',
        articles=articles,
        categories=categories,
        selected_category=category
    )


@news_bp.route('/schemes')
def government_schemes():
    """View government schemes only."""
    schemes = NewsArticle.query.filter_by(
        category='scheme',
        is_published=True
    ).order_by(NewsArticle.published_at.desc()).all()
    
    return render_template('news/schemes.html', articles=schemes)


@news_bp.route('/<int:article_id>')
def view_article(article_id):
    """View single article."""
    article = NewsArticle.query.get_or_404(article_id)
    
    # Get related articles
    related = NewsArticle.query.filter_by(
        category=article.category,
        is_published=True
    ).filter(NewsArticle.id != article_id).limit(3).all()
    
    return render_template('news/article.html', article=article, related=related)
