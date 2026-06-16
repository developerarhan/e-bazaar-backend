from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

from .models import Product

logger = logging.getLogger('store')


@receiver([post_save, post_delete], sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    """
    Called automatically when any product is saved or deleted.
    Clears related cache so next request gets fresh data.
    """
    # Clear this specific product
    cache.delete(f"products:detail:{instance.id}")
    
    # Clear all list pages — we don't know which page this
    # product appears on, so clear everything
    if hasattr(cache, 'delete_pattern'):
        cache.delete_pattern("ebazaar:products:list:*")
    
    else:
        # Fallback for DummyCache (tests) or LocMemCache where delete_pattern doesn't exist
        logger.debug("Cache backend does not support delete_pattern; skipping pattern invalidation.")