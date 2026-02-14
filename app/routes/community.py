"""Community routes for AgriBalance - Farmer discussions."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import json
from app import db
from app.models import CommunityPost, Comment

community_bp = Blueprint('community', __name__)

# Allowed file extensions for image uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@community_bp.route('/')
def feed():
    """Community feed - all posts."""
    category = request.args.get('category', '')
    
    query = CommunityPost.query
    
    if category:
        query = query.filter_by(category=category)
    
    # Pinned posts first, then by date
    posts = query.order_by(
        CommunityPost.is_pinned.desc(),
        CommunityPost.created_at.desc()
    ).all()
    
    categories = ['question', 'tip', 'success-story', 'discussion']
    
    return render_template(
        'community/feed.html',
        posts=posts,
        categories=categories,
        selected_category=category
    )


@community_bp.route('/post/<int:post_id>')
def view_post(post_id):
    """View single post with comments."""
    post = CommunityPost.query.get_or_404(post_id)
    
    # Increment view count
    post.views += 1
    db.session.commit()
    
    comments = post.comments.order_by(Comment.created_at.asc()).all()
    
    return render_template('community/view_post.html', post=post, comments=comments)


@community_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    """Create new community post."""
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category', 'discussion')
        
        if not title or not content:
            flash('Please fill in title and content.', 'error')
            return render_template('community/create_post.html')
        
        # Handle image uploads
        image_urls = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create unique filename
                    timestamp = str(int(os.times()[4] * 1000))
                    filename = f"{current_user.id}_{timestamp}_{filename}"
                    
                    # Create upload directory if it doesn't exist
                    upload_dir = os.path.join('app', 'static', 'uploads', 'community')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Save file
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    
                    # Store relative URL
                    image_urls.append(f"/static/uploads/community/{filename}")
        
        post = CommunityPost(
            user_id=current_user.id,
            title=title,
            content=content,
            category=category,
            images=json.dumps(image_urls) if image_urls else None
        )
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('community.view_post', post_id=post.id))
    
    return render_template('community/create_post.html')


@community_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    """Add comment to a post."""
    post = CommunityPost.query.get_or_404(post_id)
    
    content = request.form.get('content')
    if not content:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('community.view_post', post_id=post_id))
    
    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()
    
    flash('Comment added!', 'success')
    return redirect(url_for('community.view_post', post_id=post_id))


@community_bp.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    """Like a post."""
    post = CommunityPost.query.get_or_404(post_id)
    post.likes += 1
    db.session.commit()
    
    return redirect(url_for('community.view_post', post_id=post_id))


@community_bp.route('/my-posts')
@login_required
def my_posts():
    """View user's own posts."""
    posts = CommunityPost.query.filter_by(user_id=current_user.id).order_by(
        CommunityPost.created_at.desc()
    ).all()
    
    return render_template('community/my_posts.html', posts=posts)


@community_bp.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    """Edit a post."""
    post = CommunityPost.query.filter_by(
        id=post_id, user_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        post.title = request.form.get('title', post.title)
        post.content = request.form.get('content', post.content)
        post.category = request.form.get('category', post.category)
        
        db.session.commit()
        flash('Post updated!', 'success')
        return redirect(url_for('community.view_post', post_id=post.id))
    
    return render_template('community/edit_post.html', post=post)


@community_bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    """Delete a post."""
    post = CommunityPost.query.filter_by(
        id=post_id, user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted!', 'success')
    return redirect(url_for('community.feed'))
