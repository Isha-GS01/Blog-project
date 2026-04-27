from django.urls import path
from . import views, api_views

app_name = 'knowledge_base'

urlpatterns = [
    # ─────────────────────────────────────────────────────
    # PUBLIC CONTENT
    # ─────────────────────────────────────────────────────
    path('', views.post_list, name='post_list'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('search/', views.search, name='search'),
    path('users/', views.user_list, name='user_list'),

    # ─────────────────────────────────────────────────────
    # DASHBOARDS & WORKSPACE
    # ─────────────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),
    path('workspace/', views.my_workspace, name='my_workspace'),

    # ─────────────────────────────────────────────────────
    # CONTENT MANAGEMENT (Authoring)
    # ─────────────────────────────────────────────────────
    path('manage/create/', views.post_create, name='post_create'),
    path('manage/edit/<slug:slug>/', views.post_edit, name='post_edit'),
    path('manage/delete/<slug:slug>/', views.post_delete_author, name='post_delete_author'),
    path('manage/submit/<slug:slug>/', views.post_submit, name='post_submit'),
    
    # ─────────────────────────────────────────────────────
    # MODERATION WORKFLOW (Admin)
    # ─────────────────────────────────────────────────────
    path('manage/approve-queue/', views.approval_queue, name='approval_queue'),
    path('manage/approval/<slug:slug>/approve/', views.post_approve, name='post_approve'),
    path('manage/approval/<slug:slug>/reject/', views.post_reject, name='post_reject'),
    
    # Comment Moderation
    path('manage/comments/pending/', views.pending_comments, name='pending_comments'),
    path('manage/comments/toggle/<int:comment_id>/', views.toggle_comment_approval, name='toggle_comment_approval'),

    # ─────────────────────────────────────────────────────
    # SOCIAL INTERACTIONS
    # ─────────────────────────────────────────────────────
    path('post/<slug:slug>/upvote/', views.post_upvote, name='post_upvote'),
    path('post/<slug:slug>/comment/', views.add_comment, name='add_comment'),

    # ─────────────────────────────────────────────────────
    # AUTHENTICATION & PROFILE (Updated Registration Flow)
    # ─────────────────────────────────────────────────────
    path('register/',               views.register_email,   name='register'),
    path('register/verify-otp/',    views.register_otp,     name='register_otp'),
    path('register/profile/',       views.register_profile, name='register_profile'),
    
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),

    # ─────────────────────────────────────────────────────
    # API ENDPOINTS
    # ─────────────────────────────────────────────────────
    path('api/posts/', api_views.PostListCreateAPIView.as_view(), name='api_post_list'),
    path('api/posts/<int:pk>/', api_views.PostDetailAPIView.as_view(), name='api_post_detail'),
]