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

    class Meta:
        model = Order
        fields = "__all__"