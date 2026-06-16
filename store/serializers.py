from rest_framework import serializers
from .models import Product, Category, Review

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'product_count']

    def get_product_count(self, obj):
        return obj.products.count()
    

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(
        source='user.name',
        read_only=True,
    )
    user = serializers.HiddenField(
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_name',
            'rating', 'comment',
            'verified_purchase',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_name','verified_purchase']

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError(
                "Rating must be between 1 and 5."
            )
        return value
    
    def validate(self, data):
        request = self.context.get('request')
        product = self.context.get('product')

        # Check if user has already reviewed this product
        # Skip this check on update (PUT/PATCH)
        if self.instance is None:
            exists = Review.objects.filter(
                product=product,
                user=request.user,
            ).exists()
            if exists:
                raise serializers.ValidationError(
                    "You have already reviewed this product."
                )
        
        return data


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source='category.name',
        read_only=True,
        default=None,
    )
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    available_stock = serializers.IntegerField(read_only=True)
    stock_status = serializers.CharField(read_only=True)
    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price',
            'image', 'stock', 'available_stock', 'stock_status',
            'category', 'category_name',
            'average_rating', 'review_count',
            'created_at',
        ]
        read_only_fields = ['created_at', 'available_stock', 'stock_status']
