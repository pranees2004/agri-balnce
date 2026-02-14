"""Chat routes for AgriBalance - Direct messaging between users."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app import db
from app.models import Message, User

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/')
@login_required
def inbox():
    """View all conversations."""
    # Get all users the current user has messaged with
    conversations = db.session.query(User).join(
        Message, 
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == User.id),
            and_(Message.receiver_id == current_user.id, Message.sender_id == User.id)
        )
    ).distinct().all()
    
    # Get last message for each conversation
    conversation_data = []
    for user in conversations:
        last_message = Message.query.filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == user.id),
                and_(Message.receiver_id == current_user.id, Message.sender_id == user.id)
            )
        ).order_by(Message.created_at.desc()).first()
        
        # Count unread messages
        unread_count = Message.query.filter_by(
            sender_id=user.id,
            receiver_id=current_user.id,
            is_read=False
        ).count()
        
        conversation_data.append({
            'user': user,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    # Sort by last message time
    conversation_data.sort(key=lambda x: x['last_message'].created_at if x['last_message'] else None, reverse=True)
    
    return render_template('chat/inbox.html', conversations=conversation_data)


@chat_bp.route('/conversation/<int:user_id>')
@login_required
def conversation(user_id):
    """View conversation with a specific user."""
    other_user = User.query.get_or_404(user_id)
    
    if other_user.id == current_user.id:
        flash('You cannot message yourself.', 'error')
        return redirect(url_for('chat.inbox'))
    
    # Get all messages between current user and other user
    messages = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
            and_(Message.receiver_id == current_user.id, Message.sender_id == user_id)
        )
    ).order_by(Message.created_at.asc()).all()
    
    # Mark messages from other user as read
    unread_messages = Message.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user.id,
        is_read=False
    ).all()
    
    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()
    
    return render_template('chat/conversation.html', other_user=other_user, messages=messages)


@chat_bp.route('/send/<int:user_id>', methods=['POST'])
@login_required
def send_message(user_id):
    """Send a message to a user."""
    other_user = User.query.get_or_404(user_id)
    
    if other_user.id == current_user.id:
        flash('You cannot message yourself.', 'error')
        return redirect(url_for('chat.inbox'))
    
    content = request.form.get('content')
    if not content or not content.strip():
        flash('Message cannot be empty.', 'error')
        return redirect(url_for('chat.conversation', user_id=user_id))
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=user_id,
        content=content.strip()
    )
    db.session.add(message)
    db.session.commit()
    
    return redirect(url_for('chat.conversation', user_id=user_id))


@chat_bp.route('/new/<int:user_id>')
@login_required
def new_conversation(user_id):
    """Start a new conversation with a user."""
    other_user = User.query.get_or_404(user_id)
    
    if other_user.id == current_user.id:
        flash('You cannot message yourself.', 'error')
        return redirect(url_for('community.feed'))
    
    return redirect(url_for('chat.conversation', user_id=user_id))
