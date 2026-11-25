from django.db import models
from django.conf import settings


class ChatConversation(models.Model):
    """
    Stores conversation history for authenticated users.
    Anonymous users use Redis only (no persistence).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations',
        null=True, blank=True,
    )
    session_id = models.CharField(max_length=64, db_index=True)
    messages = models.JSONField(default=list)
    # messages format:
    # [
    #   {"role": "user", "content": "..."},
    #   {"role": "assistant", "content": "..."},
    # ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        who = self.user.email if self.user else f"anon:{self.session_id[:8]}"
        return f"Chat [{who}] — {self.updated_at:%Y-%m-%d %H:%M}"


class UserMemory(models.Model):
    """
    Long-term memory extracted from conversations.
    Survives across sessions — this is what makes
    the bot remember users days/weeks later.
 
    Examples of what gets stored:
      key="budget_preference"   value="under 1000"
      key="interested_in"       value="electronics, earbuds"
      key="name"                value="Rahul"
      key="last_order_concern"  value="delivery delay"
    """
    MEMORY_TYPES = [
        ('preference', 'Preference'),   # budget, brand, category
        ('interest',   'Interest'),     # product types they asked about
        ('fact',       'Fact'),         # name, city, etc.
        ('context',    'Context'),      # recent concerns / topics
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_memories',
        null=True, blank=True,
    )
    session_key = models.CharField(
        max_length=64, blank=True,
        help_text="Used for anonymous users who have no account"
    )
    memory_type = models.CharField(max_length=20, choices=MEMORY_TYPES)
    key = models.CharField(max_length=100)
    value = models.TextField()
    confidence = models.FloatField(
        default=1.0,
        help_text="How confident we are in this memory (0.0 to 1.0)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'key'],
                name='unique_user_memory_key',
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['session_key', 'key'],
                name='unique_session_memory_key',
                condition=models.Q(user__isnull=True),
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'memory_type']),
        ]

    def __str__(self):
        who = self.user.email if self.user else self.session_key[:8]
        return f"Memory [{who}] {self.key}={self.value[:30]}"


class EmbeddingDocument(models.Model):
    """
    Stores vector embeddings for RAG retrieval.
 
    Every product, FAQ, and policy gets chunked into text,
    embedded into a 384-dim vector, and stored here.
 
    At query time: user message gets embedded, cosine
    similarity search finds the most relevant documents,
    those documents get injected into the LLM prompt
    as grounding context.
 
    source_type values:
      'product' → a product from store_product
      'faq'     → a frequently asked question
      'policy'  → store policy (returns, shipping etc.)
    """
    SOURCE_TYPES = [
        ('product', 'Product'),
        ('faq',     'FAQ'),
        ('policy',  'Policy'),
    ]

    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_id = models.IntegerField(
        null=True, blank=True,
        help_text="FK to source record (product id etc.). Null for FAQs/policies."
    )

    # The actual text that was embedded
    # (stored so we can return it to the LLM as context)
    content = models.TextField()

    # The vector — pgvector VectorField
    # 384 dims matches all-MiniLM-L6-v2 output size
    # Stored as pgvector's vector type in Postgres
    embedding = models.TextField(
        help_text="Stored as comma-separated floats. Queried via raw SQL."
        # Note: we're using raw SQL for vector operations since
        # pgvector's Django integration is version-sensitive.
        # In production you'd use pgvector's VectorField — but
        # raw SQL works identically and avoids migration issues.
    )

    metadata = models.JSONField(default=dict)
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        indexes = [
            models.Index(fields=['source_type']),
            models.Index(fields=['source_type', 'source_id']),
        ]
 
    def __str__(self):
        return f"[{self.source_type}:{self.source_id}] {self.content[:60]}"
    