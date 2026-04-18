# knowledge_base/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.contrib.auth import login, logout, authenticate
from django.db.models import Q, Count, Sum
from django.db.models.functions import TruncMonth, TruncDate 
from django.utils.text import slugify
from datetime import timedelta, date 

from .models import Post, Comment, Category, ActUser
from .forms import EmployeeRegistrationForm, ActLoginForm, ProfileEditForm, PostForm

# ─────────────────────────────────────────────────────
# REUSABLE GUARDS (Decorators)
# ─────────────────────────────────────────────────────

# Custom guard for admin-only views
def admin_required_check(user):
    """Check if user is active and has admin privileges."""
    return user.is_active and getattr(user, 'is_admin_user', False)

admin_required = user_passes_test(
    admin_required_check, 
    login_url='knowledge_base:login'
)

# ─────────────────────────────────────────────────────
# HOME & SEARCH: Public/Published Content
# ─────────────────────────────────────────────────────

def post_list(request):
    """Lists all published posts, optionally filtered by category."""
    posts = Post.objects.filter(status=Post.Status.PUBLISHED).order_by('-published_at')
    categories = Category.objects.all()

    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    context = {
        'posts': posts,
        'categories': categories,
        'selected_category': category_slug,
    }
    return render(request, 'knowledge_base/post_list.html', context)


def post_detail(request, slug):
    """Displays a single published post with its approved comments."""
    post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
    comments = post.comments.filter(is_approved=True)
    has_upvoted = False
    
    if request.user.is_authenticated:
        has_upvoted = post.upvotes.filter(pk=request.user.pk).exists()

    context = {
        'post': post,
        'comments': comments,
        'has_upvoted': has_upvoted,
    }
    return render(request, 'knowledge_base/post_detail.html', context)


def search(request):
    """Global search across published posts."""
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '')
    results = Post.search(query, category_slug or None)
    categories = Category.objects.all()
    
    context = {
        'query': query,
        'results': results,
        'categories': categories,
        'selected_category': category_slug,
    }
    return render(request, 'knowledge_base/search.html', context)


# ─────────────────────────────────────────────────────
# CONTENT CREATION: Drafts and Editing
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def post_create(request):
    """Handles creating a new post draft."""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.status = Post.Status.DRAFT  # FIXED: Use enum instead of string
            
            post.slug = slugify(post.title)
            if Post.objects.filter(slug=post.slug).exists():
                post.slug = f"{post.slug}-{timezone.now().strftime('%f')}"
            
            post.save()
            form.save_m2m()
            messages.success(request, 'Post created as draft.')
            return redirect('knowledge_base:post_detail', slug=post.slug)
    else:
        form = PostForm()
    return render(request, 'knowledge_base/post_form.html', {'form': form})


@login_required(login_url='knowledge_base:login')
def post_edit(request, slug):
    """Allows authors to edit their posts."""
    post = get_object_or_404(Post, slug=slug, author=request.user)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save()
            messages.success(request, 'Post updated successfully!')
            return redirect('knowledge_base:post_detail', slug=post.slug)
    else:
        form = PostForm(instance=post)
    return render(request, 'knowledge_base/post_form.html', {
        'form': form, 
        'post': post,
        'is_edit': True
    })


@login_required(login_url='knowledge_base:login')
def post_submit(request, slug):
    """Moves a post from Draft/Rejected to Pending Approval."""
    post = get_object_or_404(Post, slug=slug, author=request.user)
    if post.status in [Post.Status.DRAFT, Post.Status.REJECTED]:
        post.status = Post.Status.PENDING
        post.save()
        messages.success(request, f'"{post.title}" submitted for approval.')
    return redirect('knowledge_base:dashboard')


# ─────────────────────────────────────────────────────
# ADMIN WORKFLOWS: Approval & Comment Management
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
@admin_required
def approval_queue(request):
    """Queue for Admins to approve posts and comments."""
    pending_posts = Post.objects.filter(status=Post.Status.PENDING).select_related('author')
    pending_comments = Comment.objects.filter(is_approved=False).select_related('post', 'author')
    
    context = {
        'pending_posts': pending_posts,
        'pending_comments': pending_comments
    }
    return render(request, 'knowledge_base/approval_queue.html', context)


@login_required(login_url='knowledge_base:login')
@admin_required
def pending_comments(request):
    """Admin-only queue showing all unapproved comments with optimized queries."""
    unapproved_qs = (
        Comment.objects
        .filter(is_approved=False)
        .select_related('post', 'author', 'post__author')
        .order_by('-created_at')
    )

    total_pending = unapproved_qs.count()

    recently_approved = (
        Comment.objects
        .filter(is_approved=True)
        .select_related('post', 'author')
        .order_by('-created_at')
        [:20]
    )

    posts_with_pending = (
        Comment.objects
        .filter(is_approved=False)
        .values('post__id', 'post__title', 'post__slug')
        .annotate(pending_count=Count('id'))
        .order_by('-pending_count')
    )

    context = {
        'unapproved_comments': unapproved_qs,
        'recently_approved': recently_approved,
        'total_pending': total_pending,
        'posts_with_pending': posts_with_pending,
    }
    return render(request, 'knowledge_base/pending_comments.html', context)


@login_required(login_url='knowledge_base:login')
@admin_required
def toggle_comment_approval(request, comment_id):
    """Flips is_approved on a single comment."""
    if request.method != 'POST':
        return redirect('knowledge_base:pending_comments')

    comment = get_object_or_404(
        Comment.objects.select_related('post', 'author'),
        id=comment_id
    )

    action = request.POST.get('action') 
    redirect_to = request.POST.get('next', 'pending_comments')

    if action == 'approve':
        comment.is_approved = True
        comment.save(update_fields=['is_approved'])
        messages.success(request, f'Comment by {comment.author.email} approved.')
    elif action == 'reject':
        comment.is_approved = False
        comment.save(update_fields=['is_approved'])
        messages.warning(request, f'Comment by {comment.author.email} rejected.')

    if redirect_to == 'post_detail':
        return redirect('knowledge_base:post_detail', slug=comment.post.slug)
    return redirect('knowledge_base:pending_comments')


@login_required(login_url='knowledge_base:login')
@admin_required
def bulk_comment_action(request):
    """Approve or reject multiple comments at once."""
    if request.method != 'POST':
        return redirect('knowledge_base:pending_comments')

    action = request.POST.get('bulk_action')
    comment_ids = request.POST.getlist('comment_ids')

    if not comment_ids:
        messages.warning(request, 'No comments selected.')
        return redirect('knowledge_base:pending_comments')

    try:
        id_list = [int(cid) for cid in comment_ids]
    except (ValueError, TypeError):
        messages.error(request, 'Invalid selection.')
        return redirect('knowledge_base:pending_comments')

    if action == 'approve':
        updated = Comment.objects.filter(id__in=id_list).update(is_approved=True)
        messages.success(request, f'{updated} comments approved.')
    elif action == 'reject':
        updated = Comment.objects.filter(id__in=id_list).update(is_approved=False)
        messages.warning(request, f'{updated} comments rejected.')

    return redirect('knowledge_base:pending_comments')


@login_required(login_url='knowledge_base:login')
@admin_required
def post_approve(request, slug):
    """Approve and publish a pending post."""
    post = get_object_or_404(Post, slug=slug, status=Post.Status.PENDING)
    post.status = Post.Status.PUBLISHED
    post.published_at = timezone.now()
    post.save()
    messages.success(request, f'"{post.title}" published.')
    return redirect('knowledge_base:approval_queue')


@login_required(login_url='knowledge_base:login')
@admin_required
def post_reject(request, slug):
    """Reject a pending post and send it back to author."""
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug, status=Post.Status.PENDING)
        post.status = Post.Status.REJECTED
        post.rejection_reason = request.POST.get('reason', '').strip()
        post.save()
        messages.warning(request, 'Post rejected and returned to author.')
    return redirect('knowledge_base:approval_queue')


# ─────────────────────────────────────────────────────
# DASHBOARDS & ANALYTICS
# ──────────────────────────────────��──────────────────

@login_required(login_url='knowledge_base:login')
def dashboard(request):
    """User personal workspace with personal stats."""
    user_posts = Post.objects.filter(author=request.user)
    
    stats = {
        'total': user_posts.count(),
        'published': user_posts.filter(status=Post.Status.PUBLISHED).count(),
        'drafts': user_posts.filter(status=Post.Status.DRAFT).count(),
        'pending': user_posts.filter(status=Post.Status.PENDING).count(),  # FIXED: Added PENDING
        'rejected': user_posts.filter(status=Post.Status.REJECTED).count(),
        'total_likes': user_posts.aggregate(total=Count('upvotes'))['total'] or 0
    }

    context = {
        'stats': stats,
        'draft_posts': user_posts.filter(status=Post.Status.DRAFT),
        'pending_posts': user_posts.filter(status=Post.Status.PENDING),
        'published_posts': user_posts.filter(status=Post.Status.PUBLISHED),
        'rejected_posts': user_posts.filter(status=Post.Status.REJECTED),
    }
    return render(request, 'knowledge_base/dashboard.html', context)


@login_required(login_url='knowledge_base:login')
def analytics_dashboard(request):
    """Global analytics dashboard for trends."""
    now = timezone.now()
    
    # FIXED: Use enum values instead of strings
    total_posts = Post.objects.filter(status=Post.Status.PUBLISHED).count()
    total_authors = ActUser.objects.filter(is_active=True).count()
    total_upvotes = (
        Post.objects
        .filter(status=Post.Status.PUBLISHED)
        .annotate(uc=Count('upvotes'))
        .aggregate(total=Sum('uc'))['total'] or 0
    )

    top_authors = (
        ActUser.objects
        .annotate(post_count=Count('posts', filter=Q(posts__status=Post.Status.PUBLISHED)))
        .filter(post_count__gt=0)
        .order_by('-post_count')[:5]
    )
    
    top_posts_alltime = (
        Post.objects
        .filter(status=Post.Status.PUBLISHED)
        .annotate(upvote_count=Count('upvotes'))
        .order_by('-upvote_count')[:6]
    )

    context = {
        'total_posts': total_posts,
        'total_authors': total_authors,
        'total_upvotes': total_upvotes,
        'top_posts_alltime': top_posts_alltime,
        'top_authors': top_authors,
        'now': now,
    }
    return render(request, 'knowledge_base/analytics_dashboard.html', context)


@login_required(login_url='knowledge_base:login')
def my_workspace(request):
    """Personal dashboard for the logged-in employee."""
    user = request.user
    now = timezone.now()
    today = now.date()

    status_counts_qs = user.posts.values('status').annotate(count=Count('id'))
    status_counts = {row['status']: row['count'] for row in status_counts_qs}

    context = {
        'user': user,
        'posts_total': sum(status_counts.values()),
        'posts_published': status_counts.get(Post.Status.PUBLISHED, 0),  # FIXED: Use enum
        'posts_draft': status_counts.get(Post.Status.DRAFT, 0),  # FIXED: Use enum
        'posts_pending': status_counts.get(Post.Status.PENDING, 0),  # FIXED: Use enum
        'posts_rejected': status_counts.get(Post.Status.REJECTED, 0),  # FIXED: Use enum
        'top_posts': (
            user.posts
            .filter(status=Post.Status.PUBLISHED)
            .annotate(like_count=Count('upvotes'))
            .order_by('-like_count')[:5]
        ),
    }
    return render(request, 'knowledge_base/my_workspace.html', context)


# ─────────────────────────────────────────────────────
# AUTHENTICATION & PROFILE
# ─────────────────────────────────────────────────────

def register(request):
    """User registration for new employees."""
    if request.user.is_authenticated:
        return redirect('knowledge_base:post_list')
    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}!')
            return redirect('knowledge_base:post_list')
    else:
        form = EmployeeRegistrationForm()
    return render(request, 'knowledge_base/auth/register.html', {'form': form})


def user_login(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('knowledge_base:post_list')
    if request.method == 'POST':
        form = ActLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, 'Logged in successfully!')
            return redirect('knowledge_base:post_list')
    else:
        form = ActLoginForm(request)
    return render(request, 'knowledge_base/auth/login.html', {'form': form})


def user_logout(request):
    """User logout view."""
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'Logged out successfully!')
    return redirect('knowledge_base:post_list')


@login_required(login_url='knowledge_base:login')
def profile(request):
    """User profile editing view."""
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('knowledge_base:profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'knowledge_base/auth/profile.html', {'form': form})


# ─────────────────────────────────────────────────────
# SOCIAL INTERACTIONS
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def post_upvote(request, slug):
    """Toggle upvote on a published post."""
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
        if post.upvotes.filter(pk=request.user.pk).exists():
            post.upvotes.remove(request.user)
            messages.info(request, 'Upvote removed.')
        else:
            post.upvotes.add(request.user)
            messages.success(request, 'Post upvoted!')
    return redirect('knowledge_base:post_detail', slug=slug)


@login_required(login_url='knowledge_base:login')
def add_comment(request, slug):
    """Add a comment to a published post."""
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
        body = request.POST.get('body', '').strip()
        if body:
            Comment.objects.create(post=post, author=request.user, body=body)
            messages.success(request, 'Comment submitted! It will appear after admin approval.')
        else:
            messages.warning(request, 'Comment cannot be empty.')
    return redirect('knowledge_base:post_detail', slug=slug)


@login_required(login_url='knowledge_base:login')
def user_list(request):
    """Display list of all active users."""
    users = ActUser.objects.filter(is_active=True).order_by('-date_joined')
    context = {
        'users': users
    }
    return render(request, 'knowledge_base/user_list.html', context)