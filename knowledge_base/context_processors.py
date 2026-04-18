# knowledge_base/context_processors.py

from .models import Comment

def pending_comment_count(request):
    """Add pending comment count to template context for admins."""
    if request.user.is_authenticated and getattr(request.user, 'is_admin_user', False):
        return {'pending_count': Comment.objects.filter(is_approved=False).count()}
    return {'pending_count': 0}