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
from django.core.mail import send_mail
from django.conf import settings

# Models and Forms
from .models import Post, Comment, Category, ActUser, PostUpvote, OTPVerification
from .forms import (
    RegistrationEmailForm, OTPVerificationForm, RegistrationProfileForm,
    ActLoginForm, ProfileEditForm, PostForm
)

# ─────────────────────────────────────────────────────
# HELPERS & GUARDS
# ─────────────────────────────────────────────────────

def is_admin(user):
    return user.is_active and (user.is_staff or user.is_superuser)

def get_pending_counts(request):
    context = {}
    if request.user.is_authenticated:
        if is_admin(request.user):
            context['pending_count'] = Comment.objects.filter(is_approved=False).count()
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
    now = timezone.now()
    last_30_days = now - timedelta(days=30)

    creation_qs = (
        Post.objects.filter(published_at__gte=last_30_days, status=Post.Status.PUBLISHED)
        .annotate(day=TruncDate('published_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )
    comments_qs = (
        Comment.objects.filter(created_at__gte=last_30_days, is_approved=True)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )
    upvotes_qs = (
        PostUpvote.objects.filter(created_at__gte=last_30_days)
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(count=Count('id')).order_by('day')
    )

    content_creation_labels = [x['day'].strftime('%Y-%m-%d') for x in creation_qs]
    content_creation_data   = [x['count'] for x in creation_qs]

    engagement_labels = sorted(
        set([x['day'].strftime('%Y-%m-%d') for x in comments_qs] +
            [x['day'].strftime('%Y-%m-%d') for x in upvotes_qs])
    )
    comments_map = {x['day'].strftime('%Y-%m-%d'): x['count'] for x in comments_qs}
    upvotes_map  = {x['day'].strftime('%Y-%m-%d'): x['count'] for x in upvotes_qs}
    engagement_comments_data = [comments_map.get(d, 0) for d in engagement_labels]
    engagement_upvotes_data  = [upvotes_map.get(d, 0) for d in engagement_labels]

    total_posts = Post.objects.filter(status=Post.Status.PUBLISHED).count()
    total_users = ActUser.objects.count()
    total_views = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .aggregate(total=Sum('views_count'))['total'] or 0
    )

    published_annotated = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related('author', 'category')
        .annotate(
            upvote_count=Count('upvotes', distinct=True),
            comment_count=Count('comments', filter=Q(comments__is_approved=True), distinct=True),
        )
    )

    context = {
        'total_posts': total_posts,
        'total_users': total_users,
        'total_views': total_views,
        'top_posts_views':    published_annotated.order_by('-views_count', '-published_at')[:5],
        'top_posts_upvoted':  published_annotated.order_by('-upvote_count', '-published_at')[:5],
        'top_posts_comments': published_annotated.order_by('-comment_count', '-published_at')[:5],
        'recent_posts': Post.objects.filter(author=request.user).order_by('-created_at')[:10],
        'content_creation_labels': json.dumps(content_creation_labels),
        'content_creation_data':   json.dumps(content_creation_data),
        'engagement_labels':         json.dumps(engagement_labels),
        'engagement_comments_data':  json.dumps(engagement_comments_data),
        'engagement_upvotes_data':   json.dumps(engagement_upvotes_data),
    }
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/dashboard.html', context)

# ─────────────────────────────────────────────────────
# PUBLIC CONTENT (Feed & Detail)
# ─────────────────────────────────────────────────────

def post_list(request):
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
    queryset = Post.objects.select_related('author', 'category').prefetch_related('tags')
    if request.user.is_authenticated and is_admin(request.user):
        post = get_object_or_404(queryset, slug=slug)
    else:
        post = get_object_or_404(queryset, slug=slug, status=Post.Status.PUBLISHED)

    if post.status == Post.Status.PUBLISHED:
        Post.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)
        post.refresh_from_db(fields=['views_count'])

    comments    = post.comments.filter(is_approved=True).select_related('author').order_by('-created_at')
    has_upvoted = request.user.is_authenticated and PostUpvote.objects.filter(post=post, user=request.user).exists()
    related_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED, category=post.category)
        .exclude(pk=post.pk)
        .annotate(
            upvote_count=Count('upvotes', distinct=True),
            comment_count=Count('comments', filter=Q(comments__is_approved=True), distinct=True),
        )
        .order_by('-published_at')[:4]
    )
    context = {'post': post, 'comments': comments, 'has_upvoted': has_upvoted, 'related_posts': related_posts}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/post_detail.html', context)

# ─────────────────────────────────────────────────────
# SEARCH, PROFILE & WORKSPACE
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def search(request):
    query        = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    posts = Post.objects.filter(status=Post.Status.PUBLISHED).select_related('author', 'category')
    if query:
        posts = posts.filter(
            Q(title__icontains=query) | Q(body__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(author__first_name__icontains=query) | Q(author__last_name__icontains=query)
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
    users = ActUser.objects.filter(is_active=True).order_by('first_name')
    context = {'users': users}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/user_list.html', context)

@login_required(login_url='knowledge_base:login')
def profile(request):
    context = {'profile_user': request.user}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/auth/profile.html', context)

@login_required(login_url='knowledge_base:login')
def my_workspace(request):
    my_posts = Post.objects.filter(author=request.user).order_by('-updated_at')
    context = {
        'my_posts': my_posts,
        'draft_count':     my_posts.filter(status=Post.Status.DRAFT).count(),
        'pending_count':   my_posts.filter(status=Post.Status.PENDING).count(),
        'published_count': my_posts.filter(status=Post.Status.PUBLISHED).count(),
    }
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/my_workspace.html', context)

# ─────────────────────────────────────────────────────
# CONTENT ACTIONS
# ─────────────────────────────────────────────────────

@login_required(login_url='knowledge_base:login')
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            base_slug = slugify(post.title)
            slug, counter = base_slug, 1
            while Post.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"; counter += 1
            post.slug = slug
            if request.user.is_staff or request.user.is_superuser:
                post.status = Post.Status.PUBLISHED
                post.published_at = timezone.now()
                msg = '✅ Post published successfully!'
            else:
                post.status = Post.Status.PENDING
                msg = '⏳ Post submitted for review. Waiting for admin approval...'
            post.save()
            form.save_m2m()
            messages.success(request, msg)
            return redirect('knowledge_base:post_list')
    else:
        form = PostForm()
    context = {'form': form, 'is_edit': False}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/post_form.html', context)

@login_required(login_url='knowledge_base:login')
def post_edit(request, slug):
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
    post = get_object_or_404(Post, slug=slug, author=request.user)
    if request.method == 'POST':
        title = post.title; post.delete()
        messages.success(request, f'🗑️ Post "{title}" has been deleted.')
        return redirect('knowledge_base:my_workspace')
    context = {'post': post}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/post_confirm_delete.html', context)

@login_required(login_url='knowledge_base:login')
def post_submit(request, slug):
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
    pending_posts = (
        Post.objects.filter(status=Post.Status.PENDING)
        .select_related('author', 'category').order_by('-created_at')
    )
    context = {'pending_posts': pending_posts}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/approval_queue.html', context)

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def post_approve(request, slug):
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug)
        post.status = Post.Status.PUBLISHED
        post.published_at = timezone.now()
        post.rejection_reason = ''
        post.save(update_fields=['status', 'published_at', 'rejection_reason'])
        messages.success(request, f'✅ "{post.title}" published successfully!')
    return redirect('knowledge_base:approval_queue')

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def post_reject(request, slug):
    if request.method == 'POST':
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
    comments = (
        Comment.objects.filter(is_approved=False)
        .select_related('post', 'author').order_by('-created_at')
    )
    context = {'comments': comments}
    context.update(get_pending_counts(request))
    return render(request, 'knowledge_base/pending_comments.html', context)

@login_required(login_url='knowledge_base:login')
@user_passes_test(is_admin)
def toggle_comment_approval(request, comment_id):
    if request.method == 'POST':
        comment = get_object_or_404(Comment, id=comment_id)
        if request.POST.get('action') == 'approve':
            comment.is_approved = True; comment.save()
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
    post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
    upvote, created = PostUpvote.objects.get_or_create(post=post, user=request.user)
    if not created:
        upvote.delete(); messages.info(request, '👎 Upvote removed.')
    else:
        messages.success(request, '👍 Post upvoted!')
    return redirect('knowledge_base:post_detail', slug=slug)

@login_required(login_url='knowledge_base:login')
def add_comment(request, slug):
    if request.method == 'POST':
        post = get_object_or_404(Post, slug=slug, status=Post.Status.PUBLISHED)
        body = request.POST.get('body', '').strip()
        if body:
            Comment.objects.create(post=post, author=request.user, body=body)
            messages.info(request, '💬 Comment submitted and awaiting approval.')
        else:
            messages.warning(request, '⚠️ Comment cannot be empty.')
    return redirect('knowledge_base:post_detail', slug=slug)

# ─────────────────────────────────────────────────────
# REGISTRATION — 3-STEP OTP FLOW
# ─────────────────────────────────────────────────────

def register_email(request):
    """
    STEP 1 — Collect email, validate it's @actcorp.in and not taken,
    then send an OTP and redirect to the verification screen.
    """
    if request.user.is_authenticated:
        return redirect('knowledge_base:post_list')

    if request.method == 'POST':
        form = RegistrationEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Generate OTP and persist the email in the session
            code = OTPVerification.generate_for(email)
            request.session['reg_email'] = email

            # Send OTP email
            try:
                send_mail(
                    subject='Your ACT InnerCircle Verification Code',
                    message=(
                        f'Hi,\n\n'
                        f'Your one-time verification code is: {code}\n\n'
                        f'This code is valid for 10 minutes. '
                        f'Do not share it with anyone.\n\n'
                        f'— ACT InnerCircle'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                # Development fallback: print to console
                print(f'\n[DEV OTP] Email: {email}  Code: {code}\n')

            messages.success(request, f'✉️ Verification code sent to {email}')
            return redirect('knowledge_base:register_otp')
    else:
        form = RegistrationEmailForm()

    return render(request, 'knowledge_base/auth/register.html', {
        'form': form,
        'step': 'email',
        'step_number': 1,
    })


def register_otp(request):
    """
    STEP 2 — Verify the 6-digit OTP the user received.
    On success, mark the session so step 3 is unlocked.
    """
    email = request.session.get('reg_email')
    if not email:
        messages.warning(request, 'Please start registration from the beginning.')
        return redirect('knowledge_base:register')

    if request.method == 'POST':
        # Allow user to request a new OTP
        if request.POST.get('action') == 'resend':
            code = OTPVerification.generate_for(email)
            try:
                send_mail(
                    subject='Your ACT InnerCircle Verification Code (resent)',
                    message=(
                        f'Your new code is: {code}\n\n'
                        f'Valid for 10 minutes.\n\n— ACT InnerCircle'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                print(f'\n[DEV OTP RESEND] Email: {email}  Code: {code}\n')
            messages.info(request, '📨 A new code has been sent.')
            return redirect('knowledge_base:register_otp')

        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['otp_code']
            try:
                otp_record = OTPVerification.objects.get(email=email)
            except OTPVerification.DoesNotExist:
                form.add_error('otp_code', 'No OTP found for this email. Please restart registration.')
                return render(request, 'knowledge_base/auth/register.html', {
                    'form': form, 'step': 'otp', 'email': email, 'step_number': 2,
                })

            if not otp_record.is_valid():
                form.add_error('otp_code', 'This code has expired. Please request a new one.')
            elif otp_record.otp_code != entered_code:
                form.add_error('otp_code', 'Incorrect code. Please try again.')
            else:
                # Mark OTP as used and unlock step 3
                otp_record.is_used = True
                otp_record.save(update_fields=['is_used'])
                request.session['reg_otp_verified'] = True
                return redirect('knowledge_base:register_profile')
    else:
        form = OTPVerificationForm()

    return render(request, 'knowledge_base/auth/register.html', {
        'form': form,
        'step': 'otp',
        'email': email,
        'step_number': 2,
    })


def register_profile(request):
    """
    STEP 3 — Collect name, department, and password.
    Creates the user account, logs them in, and redirects to the feed.
    """
    email    = request.session.get('reg_email')
    verified = request.session.get('reg_otp_verified', False)

    if not email or not verified:
        messages.warning(request, 'Please complete email verification first.')
        return redirect('knowledge_base:register')

    if request.method == 'POST':
        form = RegistrationProfileForm(request.POST)
        if form.is_valid():
            user = ActUser.objects.create_user(
                email      = email,
                password   = form.cleaned_data['password1'],
                first_name = form.cleaned_data['first_name'],
                last_name  = form.cleaned_data['last_name'],
                department = form.cleaned_data.get('department', ''),
                role       = ActUser.Role.EMPLOYEE,
            )
            # Clean up session keys
            del request.session['reg_email']
            del request.session['reg_otp_verified']

            login(request, user)
            messages.success(request, f'✅ Welcome to InnerCircle, {user.first_name}!')
            return redirect('knowledge_base:post_list')
    else:
        form = RegistrationProfileForm()

    return render(request, 'knowledge_base/auth/register.html', {
        'form': form,
        'step': 'profile',
        'email': email,
        'step_number': 3,
    })


def user_login(request):
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
    if request.method == 'POST':
        logout(request)
        messages.success(request, '👋 Logged out successfully.')
    return redirect('knowledge_base:post_list')
