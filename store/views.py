import logging
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework import status

from .models import Category, Product, Review
from .serializers import CategorySerializer, ProductSerializer, ReviewSerializer

logger = logging.getLogger('store')

PRODUCT_LIST_CACHE_TTL = 60 * 10    # 10 minutes
PRODUCT_DETAIL_CACHE_TTL = 60 * 30  # 30 minutes

class CategoryListView(APIView):
    """
    GET /api/store/categories/
    Returns all categories with product count.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "categories:list"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        cache.set(cache_key, serializer.data, timeout=PRODUCT_LIST_CACHE_TTL)
        return Response(serializer.data)


class ProductListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        page = request.query_params.get('page', 1)
        search = request.query_params.get('search', '')
        category_slug = request.query_params.get('category', '')
        sort = request.query_params.get('sort', '-created_at')

        # Validate sort fields
        allowed_sorts = [
            'price', '-price',
            'created_at', '-created_at',
            'title', '-title',
        ]
        if sort not in allowed_sorts:
            sort = '-created_at'

        # Different cache key for different queries
        cache_key = (
            f"products:list:page:{page}"
            f"search:{search}"
            f":category:{category_slug}"
            f":sort:{sort}"
        )

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Cache HIT for product list", extra={
                "page": page,
                "search": search,
            })
            return Response(cached_data)
        
        # Cache miss - query database
        logger.debug("Cache MISS for product list", extra={
            "page": page,
        })

        products = Product.objects.select_related('category').all()

        if search:
            products = products.filter(title__icontains=search)

        if category_slug:
            products = products.filter(category__slug=category_slug)

        products = products.order_by(sort)

        paginator = PageNumberPagination()
        paginator.page_size = 12
        result_page = paginator.paginate_queryset(products, request)
        serializer = ProductSerializer(result_page, many=True)
        response_data = paginator.get_paginated_response(serializer.data).data

        # Store in cache for 10 minutes
        cache.set(cache_key, response_data, timeout=PRODUCT_LIST_CACHE_TTL)
         
        return Response(response_data)


class ProductDetailView(APIView):
    def get(self, request, pk):
        cache_key = f"products:detail:{pk}"

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        
        product = get_object_or_404(
            Product.objects.select_related('category'),
            pk=pk
        )
        serializer = ProductSerializer(product)

        cache.set(cache_key, serializer.data, timeout=PRODUCT_DETAIL_CACHE_TTL)
        
        return Response(serializer.data)
    

class ProductStockView(APIView):
    """
    GET /api/store/<pk>/stock/
    Returns live stock count for a product.
    NOT cached — always fresh from database.
    Called by frontend to check stock before add to cart.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return Response({
            'product_id': product.id,
            'stock': product.stock,
            'reserved_stock': product.reserved_stock,
            'available_stock': product.available_stock,
            'stock_status': product.stock_status,
        })


class ReviewListCreateView(APIView):
    """
    GET  /api/store/<pk>/reviews/  — list reviews (public)
    POST /api/store/<pk>/reviews/  — create review (authenticated)
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        reviews = product.reviews.select_related('user').all()

        # Check if current user has already reviewed
        user_review = None
        if request.user.is_authenticated:
            user_review = reviews.filter(user=request.user).first()

        serializer = ReviewSerializer(
            reviews, many=True,
            context={'request':request}
        )

        return Response({
            'reviews': serializer.data,
            'average_rating': product.average_rating,
            'review_count': product.review_count,
            'user_has_reviewed': user_review is not None,
            'user_review_id': user_review.id if user_review else None,
        })
    
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        serializer = ReviewSerializer(
            data=request.data,
            context={
                'request': request,
                'product': product,
            }
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has actually purchased this product
        from orders.models import OrderItem
        verified_purchase = OrderItem.objects.filter(
            order__user=request.user,
            order__status='CONFIRMED',  # only confirmed orders count
            product=product
        ).exists()

        # Save with verified status set automatically
        serializer.save(
            product=product,
            user=request.user,
            verified_purchase=verified_purchase,
        )

         # Invalidate product cache — rating changed
        cache.delete(f"products:detail:{pk}")
        cache.delete(f"products:related:{pk}")
        cache.delete_pattern("products:list:*")

        logger.info("Review created", extra={
            'user_id': request.user.id,
            'product_id': pk,
            'rating': request.data.get('rating'),
            'verified_purchase': verified_purchase,
        })

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class ReviewDetailView(APIView):
    """
    PUT    /api/store/reviews/<pk>/  — update own review
    DELETE /api/store/reviews/<pk>/  — delete own review
    """
    permission_classes = [IsAuthenticated]

    def get_object(Review, pk, user):
        return get_object_or_404(Review, pk=pk, user=user)
    
    def put(self, request, pk):
        review = self.get_object(pk, request.user)

        serializer = ReviewSerializer(
            review,
            data=request.data,
            partial=True,
            context={'request': request, 'product': review.product}
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        
        # Invalidate cache
        cache.delete(f"products:detail:{review.product.id}")

        return Response(serializer.data)
    
    def delete(self, request, pk):
        review = self.get_object(pk, request.user)
        product_id = review.product.id
        review.delete()

        # Invalidate cache
        cache.delete(f"products:detail:{product_id}")
        cache.delete_pattern("products:list:*")

        logger.info("Review deleted", extra={
            'user_id': request.user.id,
            'product_id': product_id,
        })

        return Response(status=status.HTTP_204_NO_CONTENT)


class RelatedProductsView(APIView):
    """
    GET /api/store/<pk>/related/
    Returns products from the same category,
    excluding the current product.
    Falls back to recent products if no category.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        cache_key = f"products:related:{pk}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        
        if product.category:
            # Same category, exclude current product
            related = Product.objects.filter(
                category=product.category
            ).exclude(
                id=pk
            ).select_related('category').order_by('?')[:4]
            # order_by('?') = random order
            # so related products feel fresh on each visit
        else:
            # No category — just recent products
            related = Product.objects.exclude(
                id=pk
            ).select_related('category').order_by('-created_at')[:4]

        serializer = ProductSerializer(related, many=True)
        cache.set(cache_key, serializer.data, timeout=60 * 15)
        return Response(serializer.data)
