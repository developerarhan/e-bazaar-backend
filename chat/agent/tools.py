"""
Tool implementations — the actual functions the agent calls.

Each function:
  - Takes kwargs matching the tool's parameter schema
  - Queries the real database (Products, Orders etc.)
  - Returns a plain dict that gets serialised and sent back to the LLM
  - NEVER raises exceptions — always returns an error dict on failure
    (a crashing tool kills the whole agent loop)

Called by the orchestrator after Groq decides which tool to use.
"""

import logging
from decimal import Decimal

logger = logging.getLogger('chat')


# ── search_products ────────────────────────────────────────────────

def search_products(query: str, max_results: int = 4, **kwargs) -> dict:
    """
    Full-text + keyword search across products.
    Uses Django ORM with multi-term Q matching for reliability.
    """
    from store.models import Product
    from django.db.models import F, Q

    try:
        qs = Product.objects.select_related('category').filter(
            stock__gt=F('reserved_stock')
        )

        cleaned_query = (query or '').strip()
        if cleaned_query:
            # First check full phrase
            exact_match = qs.filter(
                Q(title__icontains=cleaned_query) | Q(description__icontains=cleaned_query)
            )
            if exact_match.exists():
                qs = exact_match
            else:
                # Fallback to term-based search for multi-word queries
                terms = [t for t in cleaned_query.split() if len(t) > 1]
                if terms:
                    term_filter = Q()
                    for term in terms:
                        term_filter |= Q(title__icontains=term) | Q(description__icontains=term)
                    qs = qs.filter(term_filter)

        products = list(qs[:max_results])

        if not products:
            return {
                "found": False,
                "message": f"No products found matching '{query}'.",
                "products": [],
            }

        return {
            "found": True,
            "count": len(products),
            "products": [_format_product(p) for p in products],
        }

    except Exception as e:
        logger.error("search_products tool failed", extra={'error': str(e)})
        return {"error": "Product search failed. Please try again."}


# ── filter_products ────────────────────────────────────────────────

def filter_products(
    category_slug: str = None,
    max_price: float = None,
    min_price: float = None,
    in_stock_only: bool = True,
    max_results: int = 5,
    **kwargs,
) -> dict:
    """
    Filters products by category and/or price range.
    """
    from store.models import Product
    from django.db.models import F

    try:
        qs = Product.objects.select_related('category').all()

        if in_stock_only:
            qs = qs.filter(stock__gt=F('reserved_stock'))

        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        if max_price is not None:
            qs = qs.filter(price__lte=Decimal(str(max_price)))

        if min_price is not None:
            qs = qs.filter(price__gte=Decimal(str(min_price)))

        # Sort by price ascending for budget searches,
        # by newest for browsing
        if max_price:
            qs = qs.order_by('price')
        else:
            qs = qs.order_by('-created_at')

        products = list(qs[:max_results])

        if not products:
            filters_used = []
            if category_slug:
                filters_used.append(f"category={category_slug}")
            if max_price:
                filters_used.append(f"max price=₹{max_price}")
            if min_price:
                filters_used.append(f"min price=₹{min_price}")

            return {
                "found": False,
                "message": (
                    f"No products found with filters: "
                    f"{', '.join(filters_used) or 'none'}."
                ),
                "products": [],
            }

        return {
            "found": True,
            "count": len(products),
            "filters_applied": {
                "category": category_slug,
                "max_price": max_price,
                "min_price": min_price,
                "in_stock_only": in_stock_only,
            },
            "products": [_format_product(p) for p in products],
        }

    except Exception as e:
        logger.error("filter_products tool failed", extra={'error': str(e)})
        return {"error": "Product filtering failed. Please try again."}


# ── get_product_details ────────────────────────────────────────────

def get_product_details(
    product_id: int = None,
    product_name: str = None,
    **kwargs,
) -> dict:
    """
    Gets full details of a specific product including
    average rating, review count, and stock status.
    """
    from store.models import Product

    try:
        if product_id:
            product = Product.objects.select_related(
                'category'
            ).get(id=product_id)

        elif product_name:
            product = Product.objects.select_related(
                'category'
            ).filter(
                title__icontains=product_name
            ).first()

            if not product:
                return {
                    "found": False,
                    "message": f"No product found matching '{product_name}'.",
                }
        else:
            return {"error": "Provide either product_id or product_name."}

        return {
            "found": True,
            "product": {
                **_format_product(product),
                "description": product.description,
                "average_rating": float(product.average_rating),
                "review_count": product.review_count,
                "total_stock": product.stock,
                "reserved_stock": product.reserved_stock,
            },
        }

    except Product.DoesNotExist:
        return {
            "found": False,
            "message": f"Product with ID {product_id} not found.",
        }
    except Exception as e:
        logger.error("get_product_details tool failed", extra={
            'error': str(e)
        })
        return {"error": "Failed to fetch product details."}


# ── get_order_status ───────────────────────────────────────────────

def get_order_status(
    order_id: int = None,
    user=None,
    **kwargs,
) -> dict:
    """
    Gets order status for the authenticated user.
    user is injected by the orchestrator — not from the LLM.
    """
    from orders.models import Order

    if not user or not user.is_authenticated:
        return {
            "error": "not_authenticated",
            "message": (
                "You need to be logged in to check order status. "
                "Please log in and try again."
            ),
        }

    try:
        if order_id:
            # Specific order — must belong to this user
            try:
                order = Order.objects.prefetch_related(
                    'items__product', 'tracking_updates'
                ).get(id=order_id, user=user)
            except Order.DoesNotExist:
                return {
                    "found": False,
                    "message": (
                        f"Order #{order_id} not found on your account. "
                        "Please check the order ID."
                    ),
                }
        else:
            # Most recent order
            order = Order.objects.prefetch_related(
                'items__product', 'tracking_updates'
            ).filter(user=user).order_by('-created_at').first()

            if not order:
                return {
                    "found": False,
                    "message": "You don't have any orders yet.",
                }

        # Format tracking history
        tracking = [
            {
                "status": t.status,
                "timestamp": t.time.strftime('%d %b %Y, %I:%M %p'),
            }
            for t in order.tracking_updates.all()
        ]

        # Format order items
        items = [
            {
                "product": item.product.title if item.product else "Unknown",
                "quantity": item.quantity,
                "price": f"₹{item.price:.2f}",
            }
            for item in order.items.all()
        ]

        return {
            "found": True,
            "order": {
                "id": order.id,
                "status": order.status,
                "status_display": order.status.replace("_", " ").title(),
                "grand_total": f"₹{order.grand_total:.2f}",
                "created_at": order.created_at.strftime('%d %B %Y'),
                "items": items,
                "tracking_history": tracking,
                "shipping_to": (
                    f"{order.shipping_name}, "
                    f"{order.shipping_city}"
                ) if order.shipping_name else "N/A",
            },
        }

    except Exception as e:
        logger.error("get_order_status tool failed", extra={
            'error': str(e),
            'user_id': user.id,
        })
        return {"error": "Failed to fetch order status."}


# ── get_recommendations ────────────────────────────────────────────

def get_recommendations(
    context: str = "",
    max_results: int = 4,
    user=None,
    **kwargs,
) -> dict:
    """
    Returns personalised product recommendations.

    Strategy:
      1. If user has memories (preferences/interests) → filter by them
      2. Otherwise → return highest-rated in-stock products
    """
    from store.models import Product
    from django.db.models import Avg, F, Value, FloatField
    from django.db.models.functions import Coalesce

    try:
        qs = Product.objects.select_related('category').filter(
            stock__gt=F('reserved_stock')
        )

        # Parse context for price hints
        if context:
            import re
            price_match = re.search(
                r'(?:under|below|max|upto)\s*[₹]?\s*(\d+)',
                context, re.IGNORECASE
            )
            if price_match:
                max_p = int(price_match.group(1))
                qs = qs.filter(price__lte=max_p)

            # Category hints
            category_keywords = {
                'electronics': 'electronics',
                'gadget': 'electronics',
                'clothing': None,   # too broad — skip
                'jewellery': 'jewellery',
                'jewelry': 'jewellery',
                'men': 'mens-clothing',
                'women': 'womens-clothing',
            }
            for keyword, slug in category_keywords.items():
                if keyword in context.lower() and slug:
                    qs = qs.filter(category__slug=slug)
                    break

        # Sort by average rating (handle NULLS properly for Postgres)
        products = list(
            qs.annotate(
                avg_rating=Coalesce(Avg('reviews__rating'), Value(0.0), output_field=FloatField())
            ).order_by('-avg_rating', '-created_at')[:max_results]
        )

        if not products:
            return {
                "found": False,
                "message": "No recommendations available right now.",
                "products": [],
            }

        return {
            "found": True,
            "count": len(products),
            "recommendation_basis": (
                "based on ratings and your preferences"
                if context else "our top-rated products"
            ),
            "products": [_format_product(p) for p in products],
        }

    except Exception as e:
        logger.error("get_recommendations tool failed", extra={
            'error': str(e)
        })
        return {"error": "Failed to get recommendations."}


# ── Helper ─────────────────────────────────────────────────────────

def _format_product(product) -> dict:
    """
    Formats a Product instance for the LLM to read.
    Keeps it concise — LLM doesn't need every field.
    """
    return {
        "id": product.id,
        "title": product.title,
        "price": f"₹{product.price:.2f}",
        "price_raw": float(product.price),
        "category": product.category.name if product.category else "General",
        "stock_status": product.stock_status.replace("_", " "),
        "available_stock": product.available_stock,
        "image": product.image,
    }


# ── Tool dispatcher ────────────────────────────────────────────────

TOOL_MAP = {
    "search_products":    search_products,
    "filter_products":    filter_products,
    "get_product_details": get_product_details,
    "get_order_status":   get_order_status,
    "get_recommendations": get_recommendations,
}


def execute_tool(tool_name: str, tool_args: dict, user=None) -> dict:
    """
    Dispatches a tool call to the correct function.
    Injects `user` into every tool (tools that don't
    need it just ignore it via **kwargs).

    Args:
        tool_name: str — name from TOOL_MAP
        tool_args: dict — params the LLM chose
        user: User instance or None

    Returns:
        dict — tool result (always a dict, never raises)
    """
    fn = TOOL_MAP.get(tool_name)

    if not fn:
        logger.warning("Unknown tool called", extra={'tool': tool_name})
        return {"error": f"Unknown tool: {tool_name}"}

    logger.info("Tool executing", extra={
        'tool': tool_name,
        'args': {k: v for k, v in tool_args.items()
                 if k not in ('password', 'token')},
        'user_id': user.id if user and user.is_authenticated else None,
    })

    try:
        result = fn(**tool_args, user=user)
        logger.info("Tool completed", extra={
            'tool': tool_name,
            'found': result.get('found', True),
        })
        return result

    except Exception as e:
        logger.error("Tool execution exception", extra={
            'tool': tool_name,
            'error': str(e),
        }, exc_info=True)
        return {"error": f"Tool {tool_name} failed unexpectedly."}
    