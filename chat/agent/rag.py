"""
RAG Retriever — finds relevant documents for a user query.
 
Flow:
  1. Embed the user's message
  2. Run cosine similarity search in pgvector
  3. Return top K results
  4. Format them as context for the LLM prompt
 
Why raw SQL for search:
  pgvector's similarity operators (<=> for cosine distance,
  <#> for inner product, <-> for L2) require special SQL
  syntax that Django ORM doesn't support natively.
  Raw SQL is the correct and standard approach here.
"""
import json
import logging
from django.db import connection
from chat.embeddings.encoder import embed_text, vector_to_pg_string
 
logger = logging.getLogger('chat')
 
# How many documents to retrieve per query
# More = richer context, longer prompt, slower response
TOP_K = 4
 
# Minimum similarity threshold (0 to 1)
MIN_SIMILARITY = 0.25

def normalize_metadata(metadata) -> dict:
    """
    Ensure metadata is always a dictionary.

    Supports dictionaries and JSON-encoded strings.
    Returns an empty dictionary for invalid or unsupported values.
    """
    if isinstance(metadata, dict):
        return metadata

    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid JSON metadata received")

    return {}

def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Finds the most semantically similar documents to the query.
 
    Args:
        query: str — the user's message
        top_k: int — number of results to return
 
    Returns:
        list of dicts:
          {
            'source_type': 'product'|'faq'|'policy',
            'source_id': int,
            'content': str,
            'metadata': dict,
            'similarity': float,
          }
    """
    query_vector = embed_text(query)
    query_vector_str = vector_to_pg_string(query_vector)

    logger.debug("RAG retrieval started", extra={
        'query': query[:50],
        'top_k': top_k,
    })

    # Step 2: pgvector cosine similarity search
    # embedding::vector casts our stored text to pgvector type
    # 1 - (embedding <=> query) converts distance to similarity
    # (cosine DISTANCE: 0=identical, 2=opposite)
    # (cosine SIMILARITY: 1=identical, -1=opposite)
    sql = """
        SELECT
            id,
            source_type,
            source_id,
            content,
            metadata,
            1 - (embedding::vector <=> %s::vector) AS similarity
        FROM chat_embeddingdocument
        WHERE 1 - (embedding::vector <=> %s::vector) > %s
        ORDER BY similarity DESC
        LIMIT %s
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                sql,
                [query_vector_str, query_vector_str, MIN_SIMILARITY, top_k]
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("pgvector search failed", extra={
            'error': str(e),
            'query': query[:50],
        })
        # Return empty — orchestrator handles missing context gracefully
        return []

    results = []
    for row in rows:
        doc_id, source_type, source_id, content, metadata, similarity = row
        results.append({
            'source_type': source_type,
            'source_id':   source_id,
            'content':     content,
            'metadata':    metadata,
            'similarity':  round(float(similarity), 3),
        })
 
    logger.debug("RAG retrieval complete", extra={
        'results_count': len(results),
        'top_similarity': results[0]['similarity'] if results else 0,
    })
 
    return results



def format_context_for_prompt(retrieved_docs: list[dict]) -> str:
    """
    Formats retrieved documents into a clean context block
    for injection into the LLM system prompt.
    """
    if not retrieved_docs:
        return ""

    lines = ["RELEVANT INFORMATION FROM OUR STORE (use this to answer):"]

    for i, doc in enumerate(retrieved_docs, 1):
        source_type = doc.get("source_type", "")
        metadata = normalize_metadata(doc.get("metadata"))
        similarity = doc.get("similarity", 0)

        if source_type == "product":
            stock_status = metadata.get("stock_status", "unknown")

            # Avoid errors if stock_status is not a string.
            if not isinstance(stock_status, str):
                stock_status = str(stock_status)

            lines.append(
                f"\n[Product {i}]\n"
                f"Name: {metadata.get('title', 'Unknown')}\n"
                f"Price: {metadata.get('price_str', 'N/A')}\n"
                f"Category: {metadata.get('category', 'N/A')}\n"
                f"Availability: {stock_status.replace('_', ' ')}\n"
                f"Stock: {metadata.get('available', '?')} units\n"
                f"Description: {str(doc.get('content', ''))[:300]}"
            )

        elif source_type == "faq":
            lines.append(
                f"\n[FAQ {i}]\n"
                f"{doc.get('content', '')}"
            )

        elif source_type == "policy":
            lines.append(
                f"\n[Store Policy {i}]\n"
                f"{doc.get('content', '')}"
            )

    lines.append(
        "\nNOTE: The items above are relevant background information retrieved from our knowledge base. "
        "Use them to answer customer questions about policies, FAQs, or featured products. "
        "If the user asks about specific products, categories, or order details not fully covered above, "
        "use the appropriate tool (search_products, filter_products, get_product_details, get_order_status) "
        "to look up real-time store data."
    )

    return "\n".join(lines)
