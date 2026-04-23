import json
from datetime import timedelta

# Django imports
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import login, logout
from django.db.models import Q, Count, Sum, F
from django.db.models.functions import TruncDate 
from django.utils.text import slugify

# Models and Forms
from .models import Post, Comment, Category, ActUser, PostUpvote
from .forms import EmployeeRegistrationForm, ActLoginForm, ProfileEditForm, PostForm

# ─────────────────────────────────────────────────────
# HELPERS & GUARDS
# ─────────────────────────────────────────────────────

def is_admin(user):
    """Check if the user has staff or superuser permissions."""
    return user.is_active and (user.is_staff or user.is_superuser)

def get_pending_counts(request):
    """Get pending posts and comments count for all views."""
    context = {}
    if request.user.is_authenticated:
        # Admin-specific: Count unapproved comments
        if is_admin(request.user):
            context['pending_count'] = Comment.objects.filter(is_approved=False).count()
        
        # User-specific: Count personal drafts for the sidebar badge
        context['draft_count'] = Post.objects.filter(
            author=request.user, 
            status=Post.Status.DRAFT
        ).count()
    return context

# ─────────────────────────────────────────────────────
# DASHBOARD (Analytics)
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def dashboard(request):
    """Dashboard featuring 30-day trends for content and engagement."""
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    # 1) Content Creation Trend (30 days) - PUBLISHED POSTS ONLY
    creation_qs = (
        Post.objects.filter(
            published_at__gte=last_30_days,
            status=Post.Status.PUBLISHED
        )
        .annotate(day=TruncDate('published_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # 2) Engagement Trend (30 days): approved comments + upvotes
    comments_qs = (
        Comment.objects.filter(created_at__gte=last_30_days, is_approved=True)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    upvotes_qs = (
        PostUpvote.objects.filter(created_at__gte=last_30_days)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    # Prepare Chart Data
    content_creation_labels = [x['day'].strftime('%Y-%m-%d') for x in creation_qs]
    content_creation_data = [x['count'] for x in creation_qs]

    engagement_labels = sorted(
        set([x['day'].strftime('%Y-%m-%d') for x in comments_qs] +
            [x['day'].strftime('%Y-%m-%d') for x in upvotes_qs])
    )
    comments_map = {x['day'].strftime('%Y-%m-%d'): x['count'] for x in comments_qs}
    upvotes_map = {x['day'].strftime('%Y-%m-%d'): x['count'] for x in upvotes_qs}

    engagement_comments_data = [comments_map.get(d, 0) for d in engagement_labels]
    engagement_upvotes_data = [upvotes_map.get(d, 0) for d in engagement_labels]

    # Global Stats
    total_posts = Post.objects.filter(status=Post.Status.PUBLISHED).count()
    total_users = ActUser.objects.count()
    total_views = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .aggregate(total=Sum('views_count'))['total'] or 0
    )

    # Base Queryset for Published Posts with annotations
    published_annotated = Post.objects.filter(status=Post.Status.PUBLISHED).select_related('author', 'category').annotate(
        upvote_count=Count('upvotes', distinct=True),
        comment_count=Count('comments', filter=Q(comments__is_approved=True), distinct=True),
    )

    top_posts_views = published_annotated.order_by('-views_count', '-published_at')[:5]
    top_posts_upvoted = published_annotated.order_by('-upvote_count', '-published_at')[:5]
    top_posts_comments = published_annotated.order_by('-comment_count', '-published_at')[:5]
    recent_posts = Post.objects.filter(author=request.user).order_by('-created_at')[:10]

    context = {
        'total_posts': total_posts,
        'total_users': total_users,
        'total_views': total_views,
        'top_posts_views': top_posts_views,
        'top_posts_upvoted': top_posts_upvoted,
        'top_posts_comments': top_posts_comments,
        'recent_posts': recent_posts,
        'content_creation_labels': json.dumps(content_creation_labels),
        'content_creation_data': json.dumps(content_creation_data),
        'engagement_labels': json.dumps(engagement_labels),
        'engagement_comments_data': json.dumps(engagement_comments_data),
        'engagement_upvotes_data': json.dumps(engagement_upvotes_data),
    }
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/dashboard.html', context)

# ─────────────────────────────────────────────────────
# PUBLIC CONTENT (Feed & Detail)
# ─────────────────────────────────────────────────────

def post_list(request):
    """Display all published posts."""
    posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related('author', 'category')
        .prefetch_related('tags')
        .order_by('-published_at')
    )
    categories = Category.objects.all().order_by('name')
    
    context = {'posts': posts, 'categories': categories}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/post_list.html', context)

def post_detail(request, slug):
    """Display a post. Admins can preview any post; users only see published ones."""
    # Base queryset optimized for performance
    queryset = Post.objects.select_related('author', 'category').prefetch_related('tags')

    if request.user.is_authenticated and is_admin(request.user):
        # Admins can view the post regardless of its status (for preview/moderation)
        post = get_object_or_404(queryset, slug=slug)
    else:
        # Regular users and guests can only view published posts
        post = get_object_or_404(queryset, slug=slug, status=Post.Status.PUBLISHED)
    
    # Increment view count only if it's published (don't count admin previews)
    if post.status == Post.Status.PUBLISHED:
        Post.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)
        post.refresh_from_db(fields=['views_count'])

    # Get approved comments
    comments = post.comments.filter(is_approved=True).select_related('author').order_by('-created_at')
    has_upvoted = request.user.is_authenticated and PostUpvote.objects.filter(post=post, user=request.user).exists()

    # Get related posts from same category (Always published posts only)
    related_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED, category=post.category)
        .exclude(pk=post.pk)
        .annotate(
            upvote_count=Count('upvotes', distinct=True),
            comment_count=Count('comments', filter=Q(comments__is_approved=True), distinct=True),
        )
        .order_by('-published_at')[:4]
    )

    context = {
        'post': post, 
        'comments': comments, 
        'has_upvoted': has_upvoted, 
        'related_posts': related_posts
    }
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/post_detail.html', context)

# ─────────────────────────────────────────────────────
# SEARCH, PROFILE & WORKSPACE
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def search(request):
    """Search for published posts by title, body, tags, or author."""
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    posts = Post.objects.filter(status=Post.Status.PUBLISHED).select_related('author', 'category')

    if query:
        posts = posts.filter(
            Q(title__icontains=query) | 
            Q(body__icontains=query) | 
            Q(tags__name__icontains=query) |
            Q(author__first_name__icontains=query) | 
            Q(author__last_name__icontains=query)
        ).distinct()
    
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    context = {
        'query': query, 
        'results': posts.order_by('-published_at'), 
        'categories': Category.objects.all().order_by('name'), 
        'selected_category': category_slug,
    }
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/search.html', context)

@login_required(login_url='knowledge_base:login')
def user_list(request):
    """Display list of all active users."""
    users = ActUser.objects.filter(is_active=True).order_by('first_name', 'username')
    
    context = {'users': users}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/user_list.html', context)

@login_required(login_url='knowledge_base:login')
def profile(request):
    """Display user profile."""
    context = {}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/auth/profile.html', {'profile_user': request.user, **context})

@login_required(login_url='knowledge_base:login')
def my_workspace(request):
    """Display user's posts with status breakdown."""
    my_posts = Post.objects.filter(author=request.user).order_by('-updated_at')
    
    context = {
        'my_posts': my_posts,
        'draft_count': my_posts.filter(status=Post.Status.DRAFT).count(),
        'pending_count': my_posts.filter(status=Post.Status.PENDING).count(),
        'published_count': my_posts.filter(status=Post.Status.PUBLISHED).count(),
    }
    
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/my_workspace.html', context)

# ─────────────────────────────────────────────────────
# CONTENT ACTIONS (Post/Comment Management)
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def post_create(request):
    """Create a new post. Admins publish directly, authors go to PENDING."""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            
            base_slug = slugify(post.title)
            slug = base_slug
            counter = 1
            while Post.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            post.slug = slug
            
            if request.user.is_staff or request.user.is_superuser:
                post.status = Post.Status.PUBLISHED
                post.published_at = timezone.now()
                message_text = '✅ Post published successfully!'
            else:
                post.status = Post.Status.PENDING
                message_text = '⏳ Post submitted for review. Waiting for admin approval...'
            
            post.save()
            form.save_m2m()
            messages.success(request, message_text)
            return redirect('knowledge_base:post_list')
    else: 
        form = PostForm()
    
    context = {'form': form, 'is_edit': False}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/post_form.html', context)

@login_required(login_url='knowledge_base:login')
def post_edit(request, slug):
    """Authors can edit their own posts. Rejected posts revert to Draft."""
    post = get_object_or_404(Post, slug=slug, author=request.user)
    
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated_post = form.save(commit=False)
            
            if updated_post.status == Post.Status.REJECTED: 
                updated_post.status = Post.Status.DRAFT
            
            updated_post.save()
            form.save_m2m()
            messages.success(request, '✅ Post updated successfully.')
            return redirect('knowledge_base:my_workspace')
    else: 
        form = PostForm(instance=post)
    
    context = {'form': form, 'is_edit': True, 'post': post}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/post_form.html', context)

@login_required(login_url='knowledge_base:login')
def post_delete_author(request, slug):
    """Authors can delete their own posts."""
    post = get_object_or_404(Post, slug=slug, author=request.user)
    
    if request.method == 'POST':
        post_title = post.title
        post.delete()
        messages.success(request, f'🗑️ Post "{post_title}" has been deleted.')
        return redirect('knowledge_base:my_workspace')
    
    context = {'post': post}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/post_confirm_delete.html', context)

@login_required(login_url='knowledge_base:login')
def post_submit(request, slug):
    """Submit a draft post for approval."""
    post = get_object_or_404(Post, slug=slug, author=request.user)
    
    if request.method == 'POST':
        post.status = Post.Status.PENDING
        post.save(update_fields=['status'])
        messages.success(request, '⏳ Post submitted for review.')
    
    return redirect('knowledge_base:my_workspace')

# ─────────────────────────────────────────────────────
# MODERATION (Admin) - POSTS
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def approval_queue(request):
    """View all pending posts awaiting approval."""
    pending_posts = (
        Post.objects.filter(status=Post.Status.PENDING)
        .select_related('author', 'category')
        .order_by('-created_at')
    )
    
    context = {'pending_posts': pending_posts}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/approval_queue.html', context)

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def post_approve(request, slug):
    """Approve a pending post."""
    if request.method == "POST":
        post = get_object_or_404(Post, slug=slug)
        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.rejection_reason = ""
        post.save(update_fields=['status', 'published_at', 'rejection_reason'])
        messages.success(request, f'✅ "{post.title}" published successfully!')
    
    return redirect('knowledge_base:approval_queue')

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def post_reject(request, slug):
    """Reject a pending post."""
    if request.method == "POST":
        post = get_object_or_404(Post, slug=slug)
        post.status = Post.Status.REJECTED
        post.rejection_reason = request.POST.get('reason', '').strip()
        post.save(update_fields=['status', 'rejection_reason'])
        messages.warning(request, f'❌ "{post.title}" rejected.')
    
    return redirect('knowledge_base:approval_queue')

# ─────────────────────────────────────────────────────
# MODERATION (Admin) - COMMENTS
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def pending_comments(request):
    """View comments awaiting approval."""
    comments = (
        Comment.objects.filter(is_approved=False)
        .select_related('post', 'author')
        .order_by('-created_at')
    )
    
    context = {'comments': comments}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/pending_comments.html', context)

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def toggle_comment_approval(request, comment_id):
    """Approve or reject a comment."""
    if request.method == 'POST':
        comment = get_object_or_404(Comment, id=comment_id)
        if request.POST.get('action') == 'approve':
            comment.is_approved = True
            comment.save()
            messages.success(request, '✅ Comment approved!')
        else: 
            comment.delete()
            messages.info(request, '🗑️ Comment rejected.')
    
    return redirect('knowledge_base:pending_comments')

# ─────────────────────────────────────────────────────
# SOCIAL & AUTH
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def post_upvote(request, slug):
    """Toggle upvote on a post."""
    post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
    upvote, created = PostUpvote.objects.get_or_create(post=post, user=request.user)
    
    if not created: 
        upvote.delete()
        messages.info(request, '👎 Upvote removed.')
    else:
        messages.success(request, '👍 Post upvoted!')
    
    return redirect('knowledge_base:post_detail', slug=slug)

@login_required(login_url='knowledge_base:login')
def add_comment(request, slug):
    """Add a comment to a published post."""
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
        body = request.POST.get('body', '').strip()
        
        if body: 
            Comment.objects.create(post=post, author=request.user, body=body)
            messages.info(request, '💬 Comment submitted and awaiting approval.')
        else:
            messages.warning(request, '⚠️ Comment cannot be empty.')
    
    return redirect('knowledge_base:post_detail', slug=slug)

def register(request):
    """Register a new user."""
    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            messages.success(request, '✅ Registration successful!')
            return redirect('knowledge_base:post_list')
    else: 
        form = EmployeeRegistrationForm()
    
    context = {'form': form}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/auth/register.html', context)

def user_login(request):
    """Login user."""
    if request.method == 'POST':
        form = ActLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, '✅ Login successful!')
            return redirect('knowledge_base:post_list')
    else: 
        form = ActLoginForm(request)
    
    context = {'form': form}
    context.update(get_pending_counts(request))
    
    return render(request, 'knowledge_base/auth/login.html', context)

@login_required(login_url='knowledge_base:login')
def user_logout(request):
    """Logout user."""
    if request.method == 'POST': 
        logout(request)
        messages.success(request, '👋 Logged out successfully.')
    
    return redirect('knowledge_base:post_list')