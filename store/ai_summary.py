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

    return f"""Synthesize the customer reviews for the product: "{product_title}".

<reviews>
{reviews_text}
</reviews>

### RULES:
1. Base your summary ONLY on facts explicitly mentioned in <reviews>. Never assume or invent details.
2. Ignore spam, duplicate text, or irrelevant comments.
3. Provide between 1 and 3 bullet points for positive and negative sections based strictly on available data. DO NOT invent extra points to reach 3 bullets.
4. Keep every bullet point under 15 words.
5. COMPLETENESS REQUIREMENT: You MUST include ALL 4 required sections below. Never leave a section blank, stop mid-sentence, or truncate any bullet point. Every thought must be complete.
6. Output ONLY the summary starting directly with **Overall Verdict:** (no intro/outro text).

### REQUIRED OUTPUT FORMAT:
**Overall Verdict:** [1 sentence summarizing consensus — state clearly if recommended, mixed, or to be avoided]

**What Customers Love:**
[1 to 3 bullet points of recurring pros, or write "- No major highlights mentioned"]

**Common Complaints:**
[1 to 3 bullet points of recurring cons, or write "- No major complaints found"]

**Best For:** [1 sentence describing the ideal buyer profile]"""

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
                        "You are an objective, data-driven e-commerce review analyst. "
                        "Synthesize customer reviews accurately into concise summaries without conversational filler."
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
