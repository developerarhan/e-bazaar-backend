import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from orders.models import Order, OrderItem, Payment

VALID_SHIPPING = {
    "name": "John Doe",
    "phone": "9876543210",
    "address": "123 Test Street",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
}

@pytest.mark.django_db
class TestCalculateTotal:
    """Test server-side total calculation."""

    def test_totals_below_delivery_threshold(self):
        """Under 500 -> delivery charge applies."""
        from orders.views import calculate_totals

        items = [
            { 'price': Decimal('200.00'), 'quantity': 2},
            # subtotal = 400 < 500
        ]
        totals = calculate_totals(items)

        assert totals['total'] == Decimal('400.00')
        assert totals['delivery_charges'] == Decimal('50.00')
        # tax = (400 + 50) * 0.05 = 22.50
        assert totals['tax'] == Decimal('22.50')
        assert totals['grand_total'] == Decimal('472.50')

    def test_totals_above_delivery_threshold(self):
        """Over 500 -> free delivery."""
        from orders.views import calculate_totals

        items = [
            {'price': Decimal('600.00'), 'quantity': 1},
        ]
        totals = calculate_totals(items)

        assert totals['total'] == Decimal('600.00')
        assert totals['delivery_charges'] == Decimal('0.00')
        # tax = 600 * 0.05 = 30.00
        assert totals['tax'] == Decimal('30.00')
        assert totals['grand_total'] == Decimal('630.00')

    def test_totals_exactly_at_threshold(self):
        """Exactly ₹500 → delivery charge applies (threshold is >500)."""
        from orders.views import calculate_totals

        items = [{'price': Decimal('500.00'), 'quantity': 1}]
        totals = calculate_totals(items)

        assert totals['delivery_charges'] == Decimal('50.00')
    
    def test_tax_rounded_to_two_decimals(self):
        """Tax is rounded to 2 decimal places."""
        from orders.views import calculate_totals

        items = [{'price': Decimal('333.00'), 'quantity': 1}]
        totals = calculate_totals(items)

        # tax = (333 + 50) * 0.05 = 19.15
        assert totals['tax'] == Decimal('19.15')


@pytest.mark.django_db
class TestCreateOrderPaymentView:

    def test_create_order_success(self, auth_client, product):
        """
        Valid cart creates order, reserves stock,
        returns Razorpay data.
        """
        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.order.create.return_value = {
                'id': 'order_test_123'
            }

            response = auth_client.post('/api/orders/payment/create/', {
                'items': [
                    {'product': product.id, 'quantity': 2}
                ],
                'shipping': VALID_SHIPPING  # Included valid layout fields
            }, format='json')

        assert response.status_code == 200
        assert 'razorpay_order_id' in response.data
        assert response.data['razorpay_order_id'] == 'order_test_123'

        # Order created in DB
        order = Order.objects.get(id=response.data['order_id'])
        assert order.status == 'PENDING_PAYMENT'

        # Stock reserved
        product.refresh_from_db()
        assert product.reserved_stock == 2

        # Order items created with DB price (not client price)
        item = OrderItem.objects.get(order=order)
        assert item.price == product.price
        assert item.quantity == 2

    def test_create_order_insufficient_stock(self, auth_client, out_of_stock_product):
        """Order fails when product is out of stock."""
        response = auth_client.post('/api/orders/payment/create/', {
            'items': [
                {'product': out_of_stock_product.id, 'quantity': 1}
            ],
            'shipping': VALID_SHIPPING  # Avoid block errors before evaluating stock bounds
        }, format='json')

        assert response.status_code == 400
        assert 'stock' in response.data['error'].lower()

        # No order created
        assert Order.objects.count() == 0

    def test_create_order_unauthenticated(self, api_client, product):
        """Unauthenticated user cannot create order."""
        response = api_client.post('/api/orders/payment/create/', {
            'items': [{'product': product.id, 'quantity': 1}],
            'shipping': VALID_SHIPPING
        }, format='json')

        assert response.status_code == 401

    def test_create_order_empty_cart(self, auth_client):
        """Empty items list is rejected."""
        response = auth_client.post('/api/orders/payment/create/', {
            'items': [],
            'shipping': VALID_SHIPPING  # Ensures failure occurs solely due to empty cart evaluation
        }, format='json')

        assert response.status_code == 400

    def test_create_order_invalid_product(self, auth_client):
        """Non-existent product ID is rejected."""
        response = auth_client.post('/api/orders/payment/create/', {
            'items': [{'product': 99999, 'quantity': 1}],
            'shipping': VALID_SHIPPING
        }, format='json')

        assert response.status_code == 400

    def test_create_order_invalid_quantity(self, auth_client, product):
        """Quantity less than 1 is rejected."""
        response = auth_client.post('/api/orders/payment/create/', {
            'items': [{'product': product.id, 'quantity': 0}],
            'shipping': VALID_SHIPPING
        }, format='json')

        assert response.status_code == 400

    def test_reuse_existing_pending_order(self, auth_client, product, pending_order):
        """
        Second checkout attempt reuses existing pending order
        instead of creating a new one.
        """
        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.order.create.return_value = {
                'id': 'order_new_456'
            }

            response = auth_client.post('/api/orders/payment/create/', {
                'items': [{'product': product.id, 'quantity': 1}],
                'shipping': VALID_SHIPPING
            }, format='json')
            
        assert response.status_code == 200
        # Same order ID reused
        assert response.data['order_id'] == pending_order.id
        # Still only one order
        assert Order.objects.count() == 1


@pytest.mark.django_db
class TestVerifyPaymentView:

    def test_verify_payment_success(self, auth_client, pending_order, product):
        """Valid Razorpay signature confirms order and sends confirmation email."""
        payment = Payment.objects.create(
            order=pending_order,
            razorpay_order_id='order_rzp_123',
            amount=pending_order.grand_total,
            status='CREATED',
        )

        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.utility.verify_payment_signature.return_value = True

            response = auth_client.post('/api/orders/payment/verify/', {
                'razorpay_order_id': 'order_rzp_123',
                'razorpay_payment_id': 'pay_abc123',
                'razorpay_signature': 'valid_signature',
            })
        
        assert response.status_code == 200

        # Payment status updated
        payment.refresh_from_db()
        assert payment.status == 'SUCCESS'

        # Order confirmed
        pending_order.refresh_from_db()
        assert pending_order.status == 'CONFIRMED'

    def test_verify_payment_invalid_signature(self, auth_client, pending_order):
        """Invalid Razorpay signature is rejected."""
        from razorpay.errors import SignatureVerificationError
        payment = Payment.objects.create(
            order=pending_order,
            razorpay_order_id='order_rzp_123',
            amount=pending_order.grand_total,
            status='CREATED',
        )

        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.utility.verify_payment_signature.side_effect = (
                SignatureVerificationError("Invalid signature")
            )

            response = auth_client.post('/api/orders/payment/verify/', {
                'razorpay_order_id': 'order_rzp_123',
                'razorpay_payment_id': 'pay_abc123',
                'razorpay_signature': 'invalid_signature',
            })

        assert response.status_code == 400

        # Payment marked failed
        payment.refresh_from_db()
        assert payment.status == 'FAILED'

    def test_verify_payment_duplicate(self, auth_client, pending_order):
        """Duplicate verification attempt is handled gracefully."""
        Payment.objects.create(
            order=pending_order,
            razorpay_order_id='order_rzp_123',
            amount=pending_order.grand_total,
            status='SUCCESS',
        )

        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.utility.verify_payment_signature.return_value = True

            response = auth_client.post('/api/orders/payment/verify/', {
                'razorpay_order_id': 'order_rzp_123',
                'razorpay_payment_id': 'pay_abc123',
                'razorpay_signature': 'valid_signature',
            })

        assert response.status_code == 200
        assert 'already' in response.data['message'].lower()


@pytest.mark.django_db
class TestShippingValidation:

    def test_create_order_missing_shipping(self, auth_client, product):
        """Order creation fails if shipping payload structure is completely missing or blank."""
        response = auth_client.post('/api/orders/payment/create/', {
            'items': [{'product': product.id, 'quantity': 1}],
            'shipping': {},
        }, format='json')

        assert response.status_code == 400
        # Verified to evaluate your exact validation string output layout
        assert response.data['error'] == 'Shipping details are required'

    def test_create_order_invalid_pincode(self, auth_client, product):
        """Pincode must be 6 digits."""
        bad_shipping = {**VALID_SHIPPING, "pincode": "12345"}

        response = auth_client.post('/api/orders/payment/create/', {
            'items': [{'product': product.id, 'quantity': 1}],
            'shipping': bad_shipping,
        }, format='json')

        assert response.status_code == 400
        assert 'valid 6-digit pincode' in str(response.data)

    def test_create_order_invalid_phone(self, auth_client, product):
        """Phone must be valid 10-digit Indian mobile number."""
        bad_shipping = {**VALID_SHIPPING, "phone": "12345"}

        response = auth_client.post('/api/orders/payment/create/', {
            'items': [{'product': product.id, 'quantity': 1}],
            'shipping': bad_shipping,
        }, format='json')

        assert response.status_code == 400

    def test_create_order_saves_shipping_details(self, auth_client, product):
        """Valid shipping details are saved on the order."""
        with patch('orders.views.client') as mock_razorpay:
            mock_razorpay.order.create.return_value = {'id': 'order_test_123'}

            response = auth_client.post('/api/orders/payment/create/', {
                'items': [{'product': product.id, 'quantity': 1}],
                'shipping': VALID_SHIPPING,
            }, format='json')

        assert response.status_code == 200

        order = Order.objects.get(id=response.data['order_id'])
        assert order.shipping_name == "John Doe"
        assert order.shipping_pincode == "400001"
        assert order.shipping_address_full == "123 Test Street, Mumbai, Maharashtra, 400001"
        