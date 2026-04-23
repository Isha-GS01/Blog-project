# knowledge_base/serializers.py
from rest_framework import serializers
from .models import Post, Comment, Category, ActUser

# ─────────────────────────────────────────────────────
# AUTHOR SERIALIZER
# ─────────────────────────────────────────────────────
class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = ActUser
        fields = ('id', 'full_name', 'department', 'avatar')

    def get_full_name(self, obj):
        return obj.get_full_name() if hasattr(obj, 'get_full_name') else str(obj)


# ─────────────────────────────────────────────────────
# CATEGORY SERIALIZER
# ─────────────────────────────────────────────────────
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


# ─────────────────────────────────────────────────────
# COMMENT SERIALIZER
# ─────────────────────────────────────────────────────
class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'author', 'body', 'created_at')


# ─────────────────────────────────────────────────────
# POST LIST SERIALIZER (Lean version)
# ─────────────────────────────────────────────────────
class PostListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = serializers.SerializerMethodField()
    upvote_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            'id', 'title', 'slug', 'author', 'category',
            'tags', 'excerpt', 'ai_summary',
            'upvote_count', 'comment_count',
            'published_at', 'created_at',
        )

    def get_tags(self, obj):
        try:
            return list(obj.tags.names())
        except Exception:
            return []

    def get_excerpt(self, obj):
        if not obj.body:
            return ""
        return obj.body[:300] + '...' if len(obj.body) > 300 else obj.body


# ─────────────────────────────────────────────────────
# POST DETAIL SERIALIZER (Full version)
# ─────────────────────────────────────────────────────
class PostDetailSerializer(PostListSerializer):
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        # We explicitly list fields to ensure order and avoid Meta inheritance bugs
        fields = (
            'id', 'title', 'slug', 'author', 'category',
            'tags', 'body', 'excerpt', 'ai_summary',
            'upvote_count', 'comment_count', 'comments',
            'published_at', 'created_at', 'updated_at',
        )

    def get_comments(self, obj):
        # Only return approved comments (matches your business logic)
        approved = obj.comments.filter(is_approved=True)
        return CommentSerializer(approved, many=True).data


# ─────────────────────────────────────────────────────
# TOP AUTHOR SERIALIZER (For Analytics)
# ─────────────────────────────────────────────────────
class TopAuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ActUser
        fields = ('id', 'full_name', 'department', 'avatar', 'post_count')

    def get_full_name(self, obj):
        return obj.get_full_name()