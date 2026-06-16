from rest_framework import serializers

from .models import Order, OrderItem, OrderTracking

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"


class TrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTracking
        fields = ["status", "time"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    tracking_updates = TrackingSerializer(many=True, read_only=True)
    shipping_address_full = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = [
            'id', 'status',
            'total', 'delivery_charges', 'tax', 'grand_total',
            'shipping_name', 'shipping_phone',
            'shipping_address', 'shipping_city',
            'shipping_state', 'shipping_pincode',
            'shipping_address_full',
            'items', 'tracking_updates',
            'created_at',
        ]
        read_only_fields = fields
    