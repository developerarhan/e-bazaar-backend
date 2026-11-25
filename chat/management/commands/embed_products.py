"""
Management command to build/rebuild the vector store.
 
Usage:
  python manage.py embed_products              # embed everything
  python manage.py embed_products --type product
  python manage.py embed_products --type faq
  python manage.py embed_products --type policy
  python manage.py embed_products --clear      # wipe and rebuild all
 
Run this:
  1. After initial setup (before first use)
  2. After bulk product imports
  3. After updating FAQs/policies in static_content.py
  4. When the embedding model changes
"""
 
from django.core.management.base import BaseCommand
from chat.embeddings.pipeline import (
    embed_all_products,
    embed_faqs,
    embed_policies,
)
from chat.models import EmbeddingDocument
 
 
class Command(BaseCommand):
    help = 'Build or rebuild the vector embedding store for RAG'
 
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['product', 'faq', 'policy', 'all'],
            default='all',
            help='What to embed (default: all)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing embeddings before rebuilding',
        )
 
    def handle(self, *args, **options):
        embed_type = options['type']
        clear      = options['clear']
 
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                '\n🔍 e-Bazaar RAG — Embedding Pipeline\n'
            )
        )
 
        if clear:
            if embed_type == 'all':
                count = EmbeddingDocument.objects.all().delete()[0]
                self.stdout.write(f"Cleared {count} existing embeddings.")
            else:
                count = EmbeddingDocument.objects.filter(
                    source_type=embed_type
                ).delete()[0]
                self.stdout.write(
                    f"Cleared {count} existing '{embed_type}' embeddings."
                )
 
        # Run selected embedding types
        if embed_type in ('product', 'all'):
            self.stdout.write("\n📦 Embedding products...")
            try:
                created, updated = embed_all_products(verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Products: {created} new, {updated} updated"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Product embedding failed: {e}")
                )
 
        if embed_type in ('faq', 'all'):
            self.stdout.write("\n❓ Embedding FAQs...")
            try:
                count = embed_faqs(verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ FAQs: {count} embedded")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ FAQ embedding failed: {e}")
                )
 
        if embed_type in ('policy', 'all'):
            self.stdout.write("\n📋 Embedding policies...")
            try:
                count = embed_policies(verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Policies: {count} embedded")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Policy embedding failed: {e}")
                )
 
        # Summary
        total = EmbeddingDocument.objects.count()
        by_type = EmbeddingDocument.objects.values('source_type').annotate(
            count=models.Count('id')
        ) if False else None
 
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Done! Total documents in vector store: {total}"
            )
        )
        self.stdout.write(
            "\nBreakdown:\n"
            f"  Products: {EmbeddingDocument.objects.filter(source_type='product').count()}\n"
            f"  FAQs:     {EmbeddingDocument.objects.filter(source_type='faq').count()}\n"
            f"  Policies: {EmbeddingDocument.objects.filter(source_type='policy').count()}\n"
        )
        