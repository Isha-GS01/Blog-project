# knowledge_base/urls.py

from django.urls import path
from . import views
from . import api_views

app_name = 'knowledge_base'

urlpatterns = [
    # ─────────────────────────────────────────────────────────────
    # AUTHENTICATION VIEWS
    # ─────────────────────────────────────────────────────────────
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.user_login, name='login'),
    path('accounts/logout/', views.user_logout, name='logout'),
    path('accounts/profile/', views.profile, name='profile'),

    # ─────────────────────────────────────────────────────────────
    # PUBLIC / HOME VIEWS
    # ─────────────────────────────────────────────────────────────
    path('', views.post_list, name='post_list'),
    path('search/', views.search, name='search'),

    # ─────────────────────────────────────────────────────────────
    # DASHBOARD & WORKSPACE VIEWS
    # ─────────────────────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),
    path('workspace/', views.my_workspace, name='my_workspace'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('users/', views.user_list, name='user_list'),

    # ─────────────────────────────────────────────────────────────
    # ADMIN APPROVAL & MODERATION VIEWS  ✅ Changed admin/ → manage/
    # ─────────────────────────────────────────────────────────────
    path('manage/approval-queue/', views.approval_queue, name='approval_queue'),
    path('manage/comments/pending/', views.pending_comments, name='pending_comments'),
    path('manage/comments/<int:comment_id>/toggle/', views.toggle_comment_approval, name='toggle_comment_approval'),
    path('manage/comments/bulk-action/', views.bulk_comment_action, name='bulk_comment_action'),

    # ─────────────────────────────────────────────────────────────
    # POST CREATION
    # ─────────────────────────────────────────────────────────────
    path('posts/new/', views.post_create, name='post_create'),

    # ─────────────────────────────────────────────────────────────
    # POST DETAIL & ACTIONS
    # ─────────────────────────────────────────────────────────────
    path('posts/<slug:slug>/', views.post_detail, name='post_detail'),
    path('posts/<slug:slug>/edit/', views.post_edit, name='post_edit'),
    path('posts/<slug:slug>/submit/', views.post_submit, name='post_submit'),
    path('posts/<slug:slug>/approve/', views.post_approve, name='post_approve'),
    path('posts/<slug:slug>/reject/', views.post_reject, name='post_reject'),
    path('posts/<slug:slug>/upvote/', views.post_upvote, name='post_upvote'),
    path('posts/<slug:slug>/comment/', views.add_comment, name='add_comment'),

    # ─────────────────────────────────────────────────────────────
    # REST API ENDPOINTS
    # ─────────────────────────────────────────────────────────────
    path('api/posts/', api_views.api_post_list, name='api_post_list'),
    path('api/posts/top/', api_views.api_top_posts, name='api_top_posts'),
    path('api/posts/<slug:slug>/', api_views.api_post_detail, name='api_post_detail'),
    path('api/posts/<slug:slug>/generate-summary/', api_views.api_generate_summary, name='api_generate_summary'),
    path('api/authors/top/', api_views.api_top_authors, name='api_top_authors'),
    path('api/search/', api_views.api_search, name='api_search'),
    path('api/categories/', api_views.api_categories, name='api_categories'),
]