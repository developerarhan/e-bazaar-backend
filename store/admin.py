from django.contrib import admin

from .models import Category, Product, Review

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Products"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category', 'price',
        'stock', 'available_stock', 'stock_status',
        'average_rating', 'review_count',
    ]
    list_filter = ['category', 'stock']
    search_fields = ['title']
    list_editable = ['stock']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['product__title', 'user__email']
    readonly_fields = ['created_at', 'updated_at']