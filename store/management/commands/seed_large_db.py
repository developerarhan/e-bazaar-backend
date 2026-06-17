import random
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from store.models import Product, Category, Review  
from faker import Faker

User = get_user_model()

class Command(BaseCommand):
    help = "Bulk populates Neon DB with hundreds of realistic products, users, and reviews safely"

    def handle(self, *args, **kwargs):
        # 🛡️ MASTER GUARD: If data is already there, skip the entire script instantly
        if Product.objects.exists():
            self.stdout.write(self.style.SUCCESS("🛡️ Neon DB already has products. Skipping seed to prevent any duplication!"))
            return

        fake = Faker()
        self.stdout.write("🚀 Starting Mega-Data Seeding into Neon...")

        # 1. Define High-Quality Niche Categories & Image pools
        inventory_data = {
            "Electronics": {
                "desc": "Next-gen gadgets, premium audio, and smart devices.",
                "items": ["Wireless Noise-Canceling Headphones", "Mechanical Gaming Keyboard", "4K Ultra-Wide Monitor", "Smart Fitness Watch", "Portable Bluetooth Speaker", "Ergonomic Wireless Mouse", "Dual-Device Wireless Charger", "1080p Streamer Webcam"],
                "images": [
                    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
                    "https://images.unsplash.com/photo-1618384887929-16ec33fab9ef",
                    "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf",
                    "https://images.unsplash.com/photo-1523275335684-37898b6baf30",
                    "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1",
                    "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7",
                    "https://images.unsplash.com/photo-1622445262465-2481c4574875"
                ]
            },
            "Footwear": {
                "desc": "Premium sneakers, athletic running shoes, and casual boots.",
                "items": ["Air Elite Running Shoes", "Classic White Leather Sneakers", "Waterproof Trail Hiking Boots", "Urban Streetwear High-Tops", "Breathable Mesh Slips-Ons", "All-Weather Leather Loafers"],
                "images": [
                    "https://images.unsplash.com/photo-1542291026-7eec264c27ff",
                    "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519",
                    "https://images.unsplash.com/photo-1520639888713-7851133b1ed0",
                    "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a",
                    "https://images.unsplash.com/photo-1560769629-975ec94e6a86"
                ]
            },
            "Apparel": {
                "desc": "Minimalist streetwear, heavy-cotton hoodies, and essentials.",
                "items": ["Heavyweight Oversized Hoodie", "Premium Pima Cotton Tee", "Slim-Fit Cargo Joggers", "Vintage Denim Jacket", "Windbreaker Track Jacket", "Minimalist Knit Sweater"],
                "images": [
                    "https://images.unsplash.com/photo-1556821840-3a63f95609a7",
                    "https://images.unsplash.com/photo-1521572267360-ee0c2909d518",
                    "https://images.unsplash.com/photo-1542272604-787c3835535d",
                    "https://images.unsplash.com/photo-1576566588028-4147f3842f27"
                ]
            },
            "Accessories": {
                "desc": "Crafted leather goods, minimalist wallets, and daily travel packs.",
                "items": ["Water-Resistant Laptop Backpack", "Full-Grain Leather Wallet", "Stainless Steel Matte Flask", "Polarized Classic Sunglasses", "Canvas Weekend Travel Duffel"],
                "images": [
                    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62",
                    "https://images.unsplash.com/photo-1627123424574-724758594e93",
                    "https://images.unsplash.com/photo-1602143407151-7111542de6e8",
                    "https://images.unsplash.com/photo-1511499767150-a48a237f0083"
                ]
            }
        }

        # 2. Create 50 Dummy Customer Profiles Predictably
        self.stdout.write("👥 Generating dummy customer profiles...")
        dummy_users = []
        for i in range(50):
            # ✅ FIXED: Deterministic email ensures no infinite user bloating on re-runs
            email_address = f"buyer.{i}@ebazaar.test"
            
            user, created = User.objects.get_or_create(
                email=email_address,  
                defaults={
                    'name': fake.name(),
                    'is_active': True, 
                }
            )
            if created:
                user.set_password("bazaarpass123")
                user.save()
            dummy_users.append(user)

        # 3. Create Categories and Scaled Products
        total_products_created = 0
        
        for cat_name, info in inventory_data.items():
            category, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name), 'description': info['desc']}
            )

            for base_item in info['items']:
                for variation in ["Standard", "Pro Edition", "Midnight Stealth"]:
                    title = f"{base_item} ({variation})"
                    
                    product, created = Product.objects.get_or_create(
                        title=title,
                        category=category,
                        defaults={
                            'description': f"Experience premium quality with our {title}. " + fake.paragraph(nb_sentences=4),
                            'price': random.randint(299, 8999) + 0.99,
                            'image': random.choice(info['images']),
                            'stock': random.randint(10, 150),
                            'reserved_stock': 0
                        }
                    )
                    
                    if created:
                        total_products_created += 1

                        # 4. Inject Random Reviews (Only if the product was just created)
                        reviewers = random.sample(dummy_users, random.randint(2, 6))
                        for reviewer in reviewers:
                            Review.objects.get_or_create(
                                product=product,
                                user=reviewer,
                                defaults={
                                    'rating': random.choice([4, 5, 5, 5, 3, 4]),
                                    'comment': fake.sentence(nb_words=12),
                                    'verified_purchase': random.choice([True, True, False])
                                }
                            )

        self.stdout.write(
            self.style.SUCCESS(
                f"🎉 Neon DB Hydrated! Created {total_products_created} realistic variations and thousands of review data points!"
            )
        )