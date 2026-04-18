# knowledge_base/serializers.py
# WHY serializers: When Django returns a Post object, it's a Python object.
# The outside world (mobile apps, other services) speak JSON.
# Serializers handle the conversion cleanly and safely —
# you control exactly which fields are exposed.

from rest_framework import serializers
from .models import Post, Comment, Category, ActUser


# ─────────────────────────────────────────────────────
# AUTHOR SERIALIZER (nested — used inside PostSerializer)
# WHY: We never expose sensitive fields like password hashes.
# We pick exactly what's safe to share publicly.
# ─────────────────────────────────────────────────────
class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = ActUser
        fields = ('id', 'full_name', 'department', 'avatar')

    def get_full_name(self, obj):
        return obj.get_full_name()


# ─────────────────────────────────────────────────────
# CATEGORY SERIALIZER
# ─────────────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ('id', 'name', 'slug')


# ─────────────────────────────────────────────────────
# COMMENT SERIALIZER
# ─────────────────────────────────────────────────────
class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model  = Comment
        fields = ('id', 'author', 'body', 'created_at')


# ─────────────────────────────────────────────────────
# POST LIST SERIALIZER (lightweight — for list views)
# WHY two serializers for Post: The list view shows many posts,
# so we keep it lean (no full body text, no comments).
# The detail view shows one post, so we include everything.
# ─────────────────────────────────────────────────────
class PostListSerializer(serializers.ModelSerializer):
    author    = AuthorSerializer(read_only=True)
    category  = CategorySerializer(read_only=True)
    tags      = serializers.SerializerMethodField()
    upvote_count  = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    # SerializerMethodField: call a custom method to compute this value
    excerpt   = serializers.SerializerMethodField()

    class Meta:
        model  = Post
        fields = (
            'id', 'title', 'slug', 'author', 'category',
            'tags', 'excerpt', 'ai_summary',
            'upvote_count', 'comment_count',
            'published_at', 'created_at',
        )

    def get_tags(self, obj):
        # django-taggit stores tags in a special manager — we convert to a plain list
        return list(obj.tags.names())

    def get_excerpt(self, obj):
        # First 300 characters of the body as a preview
        return obj.body[:300] + '...' if len(obj.body) > 300 else obj.body


# ─────────────────────────────────────────────────────
# POST DETAIL SERIALIZER (full — for single post view)
# ─────────────────────────────────────────────────────
class PostDetailSerializer(PostListSerializer):
    comments = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ('body', 'comments', 'updated_at')

    def get_comments(self, obj):
        # Only return approved comments
        approved = obj.comments.filter(is_approved=True)
        return CommentSerializer(approved, many=True).data


# ─────────────────────────────────────────────────────
# TOP AUTHOR SERIALIZER (for analytics endpoint)
# ─────────────────────────────────────────────────────
class TopAuthorSerializer(serializers.ModelSerializer):
    full_name   = serializers.SerializerMethodField()
    post_count  = serializers.IntegerField(read_only=True)  # Annotated in the view

    class Meta:
        model  = ActUser
        fields = ('id', 'full_name', 'department', 'avatar', 'post_count')

    def get_full_name(self, obj):
        return obj.get_full_name()