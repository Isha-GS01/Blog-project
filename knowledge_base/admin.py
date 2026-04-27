from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import ActUser, Post, Comment, Category, PostUpvote, OTPVerification


# ─────────────────────────────────────────
# CUSTOM USER ADMIN
# ─────────────────────────────────────────
@admin.register(ActUser)
class ActUserAdmin(UserAdmin):
    list_display  = ('email', 'first_name', 'last_name', 'role', 'department', 'is_active', 'published_post_count')
    list_filter   = ('role', 'department', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'department')
    ordering      = ('email',)

    fieldsets = UserAdmin.fieldsets + (
        ('ACT Platform Profile', {
            'fields': ('role', 'department', 'bio', 'avatar')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('ACT Platform Profile', {
            'fields': ('email', 'first_name', 'last_name', 'role', 'department')
        }),
    )


# ─────────────────────────────────────────
# CATEGORY ADMIN
# ─────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


# ─────────────────────────────────────────
# INLINES (Upvotes & Comments)
# ─────────────────────────────────────────
class PostUpvoteInline(admin.TabularInline):
    model = PostUpvote
    extra = 0
    readonly_fields = ('user', 'created_at')
    can_delete = True

class CommentInline(admin.TabularInline):
    model   = Comment
    extra   = 0
    fields  = ('author', 'body', 'is_approved', 'created_at')
    readonly_fields = ('author', 'body', 'created_at')


# ─────────────────────────────────────────
# POST ADMIN
# ─────────────────────────────────────────
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display   = ('title', 'author', 'category', 'status', 'get_upvote_count', 'get_comment_count', 'created_at')
    list_filter    = ('status', 'category', 'created_at')
    search_fields  = ('title', 'body', 'author__email', 'author__first_name')
    prepopulated_fields = {'slug': ('title',)}
    
    # REMOVED: 'ai_summary' from readonly_fields
    readonly_fields = ('created_at', 'updated_at', 'published_at')
    
    inlines = [PostUpvoteInline, CommentInline]

    fieldsets = (
        ('Content', {
            'fields': ('title', 'slug', 'category', 'body', 'tags')
        }),
        ('Authorship & Workflow', {
            'fields': ('author', 'status', 'rejection_reason')
        }),
        # REMOVED: 'AI Intelligence' section entirely as ai_summary is gone
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )

    def get_upvote_count(self, obj):
        return obj.upvotes.count()
    get_upvote_count.short_description = 'Upvotes'

    def get_comment_count(self, obj):
        return obj.comments.count()
    get_comment_count.short_description = 'Comments'

    actions = ['approve_posts', 'reject_posts']

    @admin.action(description='✅ Approve and publish selected posts')
    def approve_posts(self, request, queryset):
        updated = queryset.filter(status=Post.Status.PENDING).update(
            status=Post.Status.PUBLISHED,
            published_at=timezone.now()
        )
        self.message_user(request, f'{updated} post(s) successfully published.')

    @admin.action(description='❌ Reject selected posts (send back to author)')
    def reject_posts(self, request, queryset):
        updated = queryset.filter(status=Post.Status.PENDING).update(
            status=Post.Status.REJECTED
        )
        self.message_user(request, f'{updated} post(s) rejected and returned to authors.')


# ─────────────────────────────────────────
# COMMENT ADMIN
# ─────────────────────────────────────────
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display  = ('author', 'post', 'is_approved', 'created_at')
    list_filter   = ('is_approved', 'created_at')
    search_fields = ('author__email', 'body', 'post__title')
    actions       = ['approve_comments']

    @admin.action(description='✅ Approve selected comments')
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} comment(s) approved.')


# ─────────────────────────────────────────
# OTP VERIFICATION ADMIN (New)
# ─────────────────────────────────────────
@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp_code', 'created_at', 'is_used')
    list_filter  = ('is_used', 'created_at')
    search_fields = ('email', 'otp_code')
    readonly_fields = ('created_at',)