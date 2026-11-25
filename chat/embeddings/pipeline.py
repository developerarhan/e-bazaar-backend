"""
Embedding Pipeline
 
Converts products, FAQs, and policies into vector embeddings
stored in the EmbeddingDocument table.
"""

import logging
from django.db import connection, transaction
from chat.models import EmbeddingDocument
from chat.embeddings.encoder import embed_text, embed_batch, vector_to_pg_string
 
logger = logging.getLogger('chat')

def format_product_for_embedding(product):
    """
    Converts a Product instance into a rich text string for embedding.
 
    IMPORTANT: What you put here determines what queries match.
    Include everything a user might search for:
      - title (exact match searches)
      - description (semantic/conceptual searches)
      - category (browsing by type)
      - price range phrasing (budget searches)
      - stock status (availability searches)
    """
    price = float(product.price)

    # Determine price range label for natural language search
    if price < 500:
        price_label = "budget-friendly affordable under 500"
    elif price < 1000:
        price_label = "mid-range under 1000"
    elif price < 2000:
        price_label = "premium under 2000"
    else:
        price_label = "luxury high-end"
 
    category_name = product.category.name if product.category else "General"
 
    # Build embedding text — designed for semantic search
    # More descriptive = better search results
    text = (
        f"Product: {product.title}. "
        f"Category: {category_name}. "
        f"Price: ₹{price:.0f}. {price_label}. "
        f"Description: {product.description}. "
        f"Availability: {product.stock_status.replace('_', ' ')}. "
        f"Stock: {product.available_stock} units available."
    )
 
    metadata = {
        "title":        product.title,
        "price":        price,
        "price_str":    f"₹{price:.2f}",
        "category":     category_name,
        "stock_status": product.stock_status,
        "available":    product.available_stock,
        "image":        product.image,
    }
 
    return text, metadata


def upsert_embedding_raw(source_type, source_id, content, vector, metadata):
    """
    Inserts or updates an embedding using raw SQL.
    Uses pgvector's vector type directly.
    """
    vector_str = vector_to_pg_string(vector)
 
    # First save the text content to Django ORM
    obj, created = EmbeddingDocument.objects.update_or_create(
        source_type=source_type,
        source_id=source_id if source_id else None,
        defaults={
            'content':  content,
            'embedding': vector_str,    # stored as text in Django model
            'metadata':  metadata,
        }
    )
    return obj, created


# ── Product indexing ───────────────────────────────────────────────
 
def embed_all_products(verbosity=1):
    """
    Embeds ALL products in the database.
    Existing embeddings are updated (not duplicated).
 
    Returns: (created_count, updated_count)
    """
    from store.models import Product
 
    products = Product.objects.select_related('category').all()
    total = products.count()
 
    if total == 0:
        logger.warning("No products found to embed.")
        return 0, 0
 
    if verbosity:
        print(f"Embedding {total} products...")
 
    # Batch embed for speed (one model call for all products)
    texts_and_meta = [format_product_for_embedding(p) for p in products]
    texts    = [t for t, _ in texts_and_meta]
    metas    = [m for _, m in texts_and_meta]
    vectors  = embed_batch(texts)
 
    created_count = 0
    updated_count = 0
 
    for product, text, metadata, vector in zip(products, texts, metas, vectors):
        _, created = upsert_embedding_raw(
            source_type='product',
            source_id=product.id,
            content=text,
            vector=vector,
            metadata=metadata,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
 
    logger.info("Product embedding complete", extra={
        'total': total,
        'created': created_count,
        'updated': updated_count,
    })
 
    if verbosity:
        print(f"✓ Created: {created_count}, Updated: {updated_count}")
 
    return created_count, updated_count
 
 
def embed_single_product(product):
    """
    Embeds or re-embeds a single product.
    Called by Django signal when a product is saved.
    """
    text, metadata = format_product_for_embedding(product)
    vector = embed_text(text)
 
    obj, created = upsert_embedding_raw(
        source_type='product',
        source_id=product.id,
        content=text,
        vector=vector,
        metadata=metadata,
    )
 
    logger.debug(
        f"Product {'created' if created else 'updated'} in vector store",
        extra={'product_id': product.id, 'title': product.title}
    )
    return obj
 
 
def delete_product_embedding(product_id):
    """
    Removes a product's embedding when the product is deleted.
    Called by Django signal.
    """
    deleted, _ = EmbeddingDocument.objects.filter(
        source_type='product',
        source_id=product_id,
    ).delete()
 
    if deleted:
        logger.debug(f"Product embedding deleted", extra={
            'product_id': product_id
        })
 
 
# ── FAQ and Policy indexing ────────────────────────────────────────
 
def embed_faqs(verbosity=1):
    """
    Embeds all FAQ entries.
    The embeddable text is the QUESTION (what users search for).
    The full answer is stored in metadata (returned to LLM).
    """
    from chat.embeddings.static_content import FAQS
 
    if verbosity:
        print(f"Embedding {len(FAQS)} FAQs...")
 
    # Delete existing FAQ embeddings first (full refresh)
    EmbeddingDocument.objects.filter(source_type='faq').delete()
 
    texts   = [faq['question'] for faq in FAQS]
    vectors = embed_batch(texts)
 
    created = 0
    for i, (faq, vector) in enumerate(zip(FAQS, vectors)):
        content = f"Q: {faq['question']}\nA: {faq['answer']}"
        metadata = {
            'question': faq['question'],
            'answer':   faq['answer'],
            'tags':     faq.get('tags', []),
        }
        upsert_embedding_raw(
            source_type='faq',
            source_id=i,    # use index as ID for FAQs
            content=content,
            vector=vector,
            metadata=metadata,
        )
        created += 1
 
    logger.info(f"FAQ embedding complete", extra={'count': created})
    if verbosity:
        print(f"✓ {created} FAQs embedded")
 
    return created
 
 
def embed_policies(verbosity=1):
    """
    Embeds store policies.
    """
    from chat.embeddings.static_content import POLICIES
 
    if verbosity:
        print(f"Embedding {len(POLICIES)} policies...")
 
    EmbeddingDocument.objects.filter(source_type='policy').delete()
 
    texts   = [p['content'] for p in POLICIES]
    vectors = embed_batch(texts)
 
    created = 0
    for i, (policy, vector) in enumerate(zip(POLICIES, vectors)):
        metadata = {
            'title': policy['title'],
            'tags':  policy.get('tags', []),
        }
        upsert_embedding_raw(
            source_type='policy',
            source_id=i,
            content=policy['content'],
            vector=vector,
            metadata=metadata,
        )
        created += 1
 
    logger.info(f"Policy embedding complete", extra={'count': created})
    if verbosity:
        print(f"✓ {created} policies embedded")
 
    return created
