import random
import string
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from taggit.managers import TaggableManager


# ──────────────────────────────────────────────────────────────────────────────
# DUMMY VALIDATOR (Required for legacy migrations)
# ──────────────────────────────────────────────────────────────────────────────
def validate_act_email(value):
    """
    DEPRECATED: This function is kept only to prevent AttributeError 
    during older migrations that reference it.
    """
    return value
# ─────────────────────────────────────────
# CUSTOM USER MANAGER
# ─────────────────────────────────────────
class ActUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        
        email = self.normalize_email(email)
        # Email domain validation removed to allow general registration
        
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        extra_fields.setdefault('is_admin_user', True)
        return self.create_user(email, password, **extra_fields)


# ─────────────────────────────────────────
# CUSTOM USER MODEL
# ─────────────────────────────────────────
class ActUser(AbstractUser):
    class Role(models.TextChoices):
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        ADMIN    = 'ADMIN',    'Admin'

    username = None
    # Validator removed to allow any email domain
    email = models.EmailField(unique=True)
    
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    is_admin_user = models.BooleanField(default=False)
    department = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = ActUserManager()

    class Meta:
        verbose_name = 'ACT Employee'
        verbose_name_plural = 'ACT Employees'

    def __str__(self):
        return self.email

    def published_post_count(self):
        """Count the number of published posts by this user."""
        return self.posts.filter(status=Post.Status.PUBLISHED).count()

    def get_full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Return the user's first name."""
        return self.first_name


# ─────────────────────────────────────────
# CATEGORY MODEL
# ─────────────────────────────────────────
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# POST MODEL
# ─────────────────────────────────────────
class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        PENDING   = 'pending',   'Pending Review'
        PUBLISHED = 'published', 'Published'
        REJECTED  = 'rejected',  'Rejected'

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField()
    
    # Media & Documents
    image_file = models.ImageField(upload_to='uploads/images/', null=True, blank=True)
    audio_file = models.FileField(upload_to='uploads/audio/', null=True, blank=True)
    video_file = models.FileField(upload_to='uploads/video/', null=True, blank=True)
    pdf_file   = models.FileField(upload_to='uploads/pdf/', null=True, blank=True)
    ppt_file   = models.FileField(upload_to='uploads/ppt/', null=True, blank=True)
    doc_file   = models.FileField(upload_to='uploads/docs/', null=True, blank=True)
    external_url = models.URLField(max_length=500, null=True, blank=True)

    # Relationships
    author = models.ForeignKey(ActUser, on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    upvotes = models.ManyToManyField(
        ActUser, 
        through='PostUpvote', 
        related_name='upvoted_posts', 
        blank=True
    )

    # Content Status & Analytics
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT, 
        db_index=True
    )
    views_count = models.PositiveIntegerField(default=0)
    rejection_reason = models.TextField(blank=True)
    
    tags = TaggableManager(blank=True)

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['views_count']),
        ]

    def __str__(self):
        return self.title

    def get_upvote_count(self):
        return self.upvotes.count()

    def get_comment_count(self):
        return self.comments.filter(is_approved=True).count()

    @classmethod
    def search(cls, query, category=None):
        qs = cls.objects.filter(status=cls.Status.PUBLISHED)
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
        if category:
            qs = qs.filter(category__slug=category)
        return qs.order_by('-published_at')


# ─────────────────────────────────────────
# POST UPVOTE (Through Model)
# ─────────────────────────────────────────
class PostUpvote(models.Model):
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='upvote_records')
    user       = models.ForeignKey(ActUser, on_delete=models.CASCADE, related_name='upvote_records')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
        ordering = ['-created_at']
        verbose_name = 'Post Upvote'
        verbose_name_plural = 'Post Upvotes'

    def __str__(self):
        return f"{self.user.email} upvoted {self.post.title}"


# ─────────────────────────────────────────
# COMMENT MODEL
# ─────────────────────────────────────────
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(ActUser, on_delete=models.CASCADE, related_name='comments')
    body = models.TextField(max_length=1000)
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved', '-created_at']),
            models.Index(fields=['post', 'is_approved']),
        ]
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'

    def __str__(self):
        return f"Comment by {self.author.email} on {self.post.title}"

    def get_author_name(self):
        return self.author.get_full_name()


# ─────────────────────────────────────────
# OTP VERIFICATION MODEL
# ─────────────────────────────────────────
class OTPVerification(models.Model):
    """
    Stores a short-lived OTP for email verification during registration.
    """
    email      = models.EmailField(unique=True)
    otp_code   = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'OTP Verification'

    def __str__(self):
        return f"OTP for {self.email}"

    @classmethod
    def generate_for(cls, email):
        code = ''.join(random.choices(string.digits, k=6))
        cls.objects.update_or_create(
            email=email,
            defaults={'otp_code': code, 'is_used': False, 'created_at': timezone.now()},
        )
        return code

    def is_valid(self):
        age = timezone.now() - self.created_at
        return (not self.is_used) and (age.total_seconds() < 600)