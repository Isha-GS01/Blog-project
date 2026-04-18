# knowledge_base/api_views.py
# WHY a separate file from views.py: Keeps HTML views and API views
# cleanly separated. views.py = returns HTML pages.
# api_views.py = returns JSON responses.

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count
from .models import Post, ActUser, Category
from .serializers import (
    PostListSerializer, PostDetailSerializer,
    TopAuthorSerializer, CategorySerializer
)


# ─────────────────────────────────────────────────────
# GET /api/posts/
# Returns all published posts (paginated, filterable by category)
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_post_list(request):
    posts = Post.objects.filter(status=Post.Status.PUBLISHED)

    # Optional category filter: /api/posts/?category=network-tips
    category_slug = request.query_params.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    # Optional tag filter: /api/posts/?tag=fibre
    tag = request.query_params.get('tag')
    if tag:
        posts = posts.filter(tags__name__in=[tag]).distinct()

    serializer = PostListSerializer(posts, many=True)
    return Response({
        'count':   posts.count(),
        'results': serializer.data,
    })


# ─────────────────────────────────────────────────────
# GET /api/posts/<slug>/
# Returns a single published post with full body + comments
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_post_detail(request, slug):
    try:
        post = Post.objects.get(slug=slug, status=Post.Status.PUBLISHED)
    except Post.DoesNotExist:
        return Response(
            {'error': 'Post not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = PostDetailSerializer(post)
    return Response(serializer.data)


# ─────────────────────────────────────────────────────
# GET /api/posts/top/
# Returns top 10 posts ranked by upvotes (Feature #6 analytics)
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_top_posts(request):
    limit = int(request.query_params.get('limit', 10))
    limit = min(limit, 50)  # Cap at 50 to prevent abuse

    top_posts = (
        Post.objects
        .filter(status=Post.Status.PUBLISHED)
        .annotate(upvote_count=Count('upvotes'))
        .order_by('-upvote_count')[:limit]
    )
    serializer = PostListSerializer(top_posts, many=True)
    return Response({'results': serializer.data})


# ─────────────────────────────────────────────────────
# GET /api/authors/top/
# Returns top 5 authors by published post count (Feature #6)
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_top_authors(request):
    limit = int(request.query_params.get('limit', 5))
    top_authors = (
        ActUser.objects
        .filter(role=ActUser.Role.EMPLOYEE)
        .annotate(post_count=Count(
            'posts',
            filter=__import__('django.db.models', fromlist=['Q']).Q(
                posts__status=Post.Status.PUBLISHED
            )
        ))
        .order_by('-post_count')[:limit]
    )
    serializer = TopAuthorSerializer(top_authors, many=True)
    return Response({'results': serializer.data})


# ─────────────────────────────────────────────────────
# GET /api/search/?q=fibre&category=network-tips
# Full-text search via API (Feature #7)
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_search(request):
    query         = request.query_params.get('q', '').strip()
    category_slug = request.query_params.get('category', '')

    if not query:
        return Response(
            {'error': 'Provide a search query using ?q=your+search+term'},
            status=status.HTTP_400_BAD_REQUEST
        )

    results    = Post.search(query, category_slug or None)
    serializer = PostListSerializer(results, many=True)
    return Response({
        'query':   query,
        'count':   results.count(),
        'results': serializer.data,
    })


# ─────────────────────────────────────────────────────
# GET /api/categories/
# List all categories
# ─────────────────────────────────────────────────────
@api_view(['GET'])
def api_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response({'results': serializer.data})


# ─────────────────────────────────────────────────────
# POST /api/posts/<slug>/generate-summary/
# Calls an AI model to generate a summary and saves it.
# Admin only — this costs API tokens so we restrict it.
# ─────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_generate_summary(request, slug):
    # Only admins can trigger AI generation
    if not request.user.is_admin_user:
        return Response(
            {'error': 'Only admins can trigger AI summary generation.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Call the AI service (defined in Step 4 below)
    from .ai_service import generate_post_summary
    try:
        summary = generate_post_summary(post)
        post.ai_summary = summary
        post.save(update_fields=['ai_summary'])
        return Response({
            'success': True,
            'slug':       post.slug,
            'ai_summary': summary,
        })
    except Exception as e:
        return Response(
            {'error': f'AI generation failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )