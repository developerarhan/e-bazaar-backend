"""
Django signals that keep embeddings in sync with the database.
 
When a product is saved → re-embed it
When a product is deleted → remove its embedding
 
This means you NEVER have stale product data in the vector store.
The chatbot always sees current prices, descriptions, stock levels.
"""
 
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
 
logger = logging.getLogger('chat')
 
 
@receiver(post_save, sender='store.Product')
def on_product_saved(sender, instance, created, **kwargs):
    """
    Automatically re-embeds a product whenever it's saved.
    Runs AFTER the save completes (post_save).
 
    Triggered by:
      - Admin panel edits
      - API updates (stock changes, price changes)
      - Management commands
    """
    try:
        from chat.embeddings.pipeline import embed_single_product
        embed_single_product(instance)
        logger.debug("Product re-embedded after save", extra={
            'product_id': instance.id,
            'created': created,
        })
    except Exception as e:
        # NEVER let an embedding failure crash a product save
        # The product saves fine — just the vector is stale
        logger.error("Failed to re-embed product after save", extra={
            'product_id': instance.id,
            'error': str(e),
        })
 
 
@receiver(post_delete, sender='store.Product')
def on_product_deleted(sender, instance, **kwargs):
    """
    Removes a product's embedding when the product is deleted.
    Prevents the chatbot recommending deleted products.
    """
    try:
        from chat.embeddings.pipeline import delete_product_embedding
        delete_product_embedding(instance.id)
    except Exception as e:
        logger.error("Failed to delete product embedding", extra={
            'product_id': instance.id,
            'error': str(e),
        })
 