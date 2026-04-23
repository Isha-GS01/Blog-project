# knowledge_base/api_views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.db.models import Count, Q
from .models import Post, ActUser, Category
from .serializers import (
    PostListSerializer, PostDetailSerializer,
    TopAuthorSerializer, CategorySerializer
)

# ─── CLASS-BASED VIEWS (Required by your urls.py) ──────────────────

class PostListCreateAPIView(generics.ListCreateAPIView):
    """Handles listing and creating posts."""
    serializer_class = PostListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Post.objects.filter(status=Post.Status.PUBLISHED)
        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class PostDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles GET, PUT, PATCH, and DELETE for a single post.
    This fixes the 'PostDetailAPIView' AttributeError.
    """
    queryset = Post.objects.filter(status=Post.Status.PUBLISHED)
    serializer_class = PostDetailSerializer
    lookup_field = 'slug'
    permission_classes = [IsAuthenticatedOrReadOnly]


# ─── FUNCTION-BASED VIEWS (For Analytics & Search) ──────────────────

@api_view(['GET'])
def api_top_posts(request):
    limit = int(request.query_params.get('limit', 10))
    top_posts = (
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .annotate(upvote_count=Count('upvotes'))
        .order_by('-upvote_count')[:limit]
    )
    serializer = PostListSerializer(top_posts, many=True)
    return Response({'results': serializer.data})

@api_view(['GET'])
def api_top_authors(request):
    limit = int(request.query_params.get('limit', 5))
    top_authors = (
        ActUser.objects.filter(role=ActUser.Role.EMPLOYEE)
        .annotate(post_count=Count('posts', filter=Q(posts__status=Post.Status.PUBLISHED)))
        .order_by('-post_count')[:limit]
    )
    serializer = TopAuthorSerializer(top_authors, many=True)
    return Response({'results': serializer.data})

@api_view(['GET'])
def api_search(request):
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'error': 'No query provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    results = Post.search(query)
    serializer = PostListSerializer(results, many=True)
    return Response({'results': serializer.data})

@api_view(['GET'])
def api_categories(request):
    categories = Category.objects.all()
    serializer = CategorySerializer(categories, many=True)
    return Response({'results': serializer.data})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_generate_summary(request, slug):
    if not getattr(request.user, 'is_admin_user', False):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        post = Post.objects.get(slug=slug)
        from .ai_service import generate_post_summary
        summary = generate_post_summary(post)
        post.ai_summary = summary
        post.save(update_fields=['ai_summary'])
        return Response({'success': True, 'ai_summary': summary})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)