"""
Generates AI-powered review summaries using Groq.

Separated from views.py because:
  - Easier to test independently
  - Easy to swap Groq for another provider later
  - Keeps views.py focused on HTTP concerns
"""

import logging
from groq import Groq
from django.conf import settings

logger = logging.getLogger('store')

class ReviewSummaryError(Exception):
    """Raised when summary generation fails."""
    pass

def build_prompt(reviews, product_title):
    """
    Builds the prompt sent to Groq.

    Good prompts for summarization are:
      - Specific about format (bullet points, length)
      - Ask for both positives AND negatives
        (pure positive summaries feel fake)
      - Ask for a verdict (saves the user time)
      - NOT too long — Groq works best with focused prompts
    """
    # Format reviews for the prompt
    # Only send what's needed — rating + comment
    # Don't send user IDs, timestamps etc (noise for the model)
    formatted_reviews = []
    for i, review in enumerate(reviews, 1):
        verified = " [Verified Purchase]" if review.verified_purchase else ""
        formatted_reviews.append(
            f"{i}. Rating: {review.rating}/5{verified}\n"
            f"   Review: {review.comment}"
        )

    reviews_text = "\n\n".join(formatted_reviews)

    return f"""You are a helpful shopping assistant. Analyze the following customer reviews for "{product_title} and provide a concise summary."

CUSTOMER REVIEWS:
{reviews_text}

Provide a structured summary in this EXACT format:
**Overall Verdict:** [One sentence — is this product worth buying?]

**What Customers Love:**
- [Key positive point 1]
- [Key positive point 2]
- [Key positive point 3 if applicable]

**Common Complaints:**
- [Key negative point 1]
- [Key negative point 2 if applicable]
- None mentioned [if no negatives found]

**Best For:** [Who should buy this product?]

Keep each bullet point under 15 words. Be honest — if reviews are mostly negative, say so."""

def generate_review_summary(reviews, product_title):
    """
    Calls Groq API and returns a formatted summary string.

    Args:
        reviews: QuerySet or list of Review instances
        product_title: str, name of the product

    Returns:
        str — formatted summary text

    Raises:
        ReviewSummaryError — if generation fails
    """
    if not settings.GROQ_API_KEY:
        raise ReviewSummaryError(
            "AI summary is not configured on this server."
        )
    
    review_list = list(reviews)

    if len(review_list) == 0:
        raise ReviewSummaryError(
            "No reviews to summarize."
        )
    
    # Don't summarize just 1-2 reviews —
    # a summary of 1 review is just... the review
    if len(review_list) < 3:
        raise ReviewSummaryError(
            f"Not enough reviews to summarize "
            f"(need at least 3, have {len(review_list)})."
        )
    
    prompt = build_prompt(review_list, product_title)

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)

        logger.info("Calling Groq API for review summary", extra={
            'product': product_title,
            'review_count': len(review_list),
            'model': settings.GROQ_MODEL,
        })

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, honest shopping assistant. "
                        "You summarize customer reviews accurately without "
                        "exaggerating positives or negatives."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=settings.GROQ_MODEL,
            temperature=0.3,    # low temperature = consistent, factual output
                                # (0 = deterministic, 1 = creative)
            max_tokens=500,  
        )

        summary = chat_completion.choices[0].message.content.strip()

        logger.info("Groq summary generated successfully", extra={
            'product': product_title,
            'summary_length': len(summary),
        })

        return summary
    
    except ReviewSummaryError:
        raise

    except Exception as exc:
        logger.error("Groq API call failed", extra={
            'product': product_title,
            'error': str(exc),
        }, exc_info=True)
        raise ReviewSummaryError(
            "Failed to generate summary. Please try again later."
        ) from exc
