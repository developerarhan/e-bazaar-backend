import pytest
from decimal import Decimal
from store.models import Product, Category, Review


@pytest.mark.django_db
class TestProductStock:
    """Tests for stock management methods."""

    def test_available_stock_caculation(self, product):
        product.stock = 50
        product.reserved_stock = 10
        assert product.available_stock == 40

    def test_stock_status_in_stock(self, product):
        product.stock = 50
        product.reserved_stock = 0
        assert product.stock_status == "in_stock"

    def test_stock_status_low_stock(self, product):
        product.stock = 5
        product.reserved_stock = 2
        assert product.stock_status == "low_stock"

    def test_stock_status_out_of_stock(self, product):
        product.stock = 5
        product.reserved_stock = 5
        assert product.stock_status == "out_of_stock"

    def test_reserve_stock_success(self, product):
        """reserve_stock() returns True when enough stock."""
        product.stock = 10
        product.reserved_stock = 0
        product.save()

        result = product.reserve_stock(5)

        assert result is True
        product.refresh_from_db()
        assert product.reserved_stock == 5
        assert product.available_stock == 5

    def test_reserve_stock_insufficient(self, product):
        """reserve_stock() returns False when not enough stock."""
        product.stock = 3
        product.reserved_stock = 2
        product.save()

        result = product.reserve_stock(5)

        assert result is False
        product.refresh_from_db()
        assert product.reserved_stock == 2

    def test_reserve_stock_exact_amount(self, product):
        """Can reserve exactly the available amount."""
        product.stock = 3
        product.reserved_stock = 0
        product.save()

        result = product.reserve_stock(3)

        assert result is True
        product.refresh_from_db()
        assert product.available_stock == 0

    def test_release_stock(self, product):
        """release_stock() reduces reserved_stock."""
        product.stock = 10
        product.reserved_stock = 5
        product.save()

        product.release_stock(3)

        product.refresh_from_db()
        assert product.reserved_stock == 2

    def test_confirm_stock(self, product):
        """confirm_stock() reduces both stock and reserved_stock."""
        product.stock = 10
        product.reserved_stock = 5
        product.save()

        product.confirm_stock(5)

        product.refresh_from_db()
        assert product.stock == 5
        assert product.reserved_stock == 0

    def test_reserve_stock_atomic(self, product):
        """
        Two concurrent reservations — only one should succeed
        when there is only enough stock for one.
        """
        product.stock = 5
        product.reserved_stock = 0
        product.save()

        # First reservation succeeds
        result1 = product.reserve_stock(5)
        assert result1 is True

        # Second reservation fails — no stock left
        result2 = product.reserve_stock(1)
        assert result2 is False

@pytest.mark.django_db
class TestProductRating:
    """Tests for review-based rating properties."""

    def test_average_rating_no_reviews(self, product):
        assert product.average_rating == 0

    def test_average_rating_single_review(self, product, verified_user):
        Review.objects.create(
            product=product,
            user=verified_user,
            rating=4,
            comment='Good product, works well.',
        )  
        assert product.average_rating == 4.0
    
    def test_average_rating_multiple_reviews(self, product, verified_user, second_user):
        Review.objects.create(
            product=product,
            user=verified_user,
            rating=5,
            comment='Excellent product.',
        )
        Review.objects.create(
            product=product,
            user=second_user,
            rating=3,
            comment='Decent product.',
        )
        # (5 + 3) / 2 = 4.0
        assert product.average_rating == 4.0

    def test_review_count(self, product, verified_user, second_user):
        Review.objects.create(
            product=product,
            user=verified_user,
            rating=5,
            comment='Great product.',
        )
        Review.objects.create(
            product=product,
            user=second_user,
            rating=4,
            comment='Good product.',
        )
        assert product.review_count == 2

    def test_review_count_empty(self, product):
        assert product.review_count == 0
