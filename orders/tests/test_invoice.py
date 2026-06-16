import pytest
from orders.invoice import generate_invoice_pdf


@pytest.mark.django_db
class TestInvoiceGeneration:

    def test_generate_invoice_returns_pdf_bytes(self, confirmed_order):
        """Invoice generation returns valid PDF bytes."""
        pdf_bytes = generate_invoice_pdf(confirmed_order)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

        # PDF files start with %PDF- magic bytes
        assert pdf_bytes[:5] == b'%PDF-'

    def test_invoice_endpoint_success(self, auth_client, confirmed_order):
        """Authenticated user can download invoice for their order."""
        response = auth_client.get(f'/api/orders/{confirmed_order.id}/invoice/')

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert 'attachment' in response['Content-Disposition']

    def test_invoice_pending_order_rejected(self, auth_client, pending_order):
        """Cannot download invoice for unpaid order."""
        response = auth_client.get(f'/api/orders/{pending_order.id}/invoice/')

        assert response.status_code == 400

    def test_invoice_other_users_order_forbidden(
        self, auth_client, second_user, product
    ):
        """User cannot download another user's invoice."""
        from orders.models import Order

        other_order = Order.objects.create(
            user=second_user,
            total=100, delivery_charges=50, tax=7.5, grand_total=157.5,
            status='CONFIRMED',
        )

        response = auth_client.get(f'/api/orders/{other_order.id}/invoice/')

        assert response.status_code == 404
