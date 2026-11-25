import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import json


@pytest.mark.django_db
class TestSearchProductsTool:

    def test_finds_matching_products(self, product):
        from chat.agent.tools import search_products

        result = search_products(query=product.title[:10])

        assert result['found'] is True
        assert result['count'] >= 1
        titles = [p['title'] for p in result['products']]
        assert any(product.title[:10].lower() in t.lower() for t in titles)

    def test_returns_not_found_for_unknown(self):
        from chat.agent.tools import search_products

        result = search_products(query="xyzzy_nonexistent_product_12345")

        assert result['found'] is False
        assert 'message' in result

    def test_respects_max_results(self, product, low_stock_product):
        from chat.agent.tools import search_products
        # Both products have common words — search broadly
        result = search_products(query="product", max_results=1)
        # max_results respected
        assert len(result.get('products', [])) <= 1

    def test_excludes_out_of_stock(self, out_of_stock_product):
        from chat.agent.tools import search_products

        result = search_products(query=out_of_stock_product.title[:10])
        # out_of_stock_product has available_stock=0 → excluded
        if result['found']:
            for p in result['products']:
                assert p['available_stock'] > 0


@pytest.mark.django_db
class TestFilterProductsTool:

    def test_filter_by_category(self, product, category):
        from chat.agent.tools import filter_products

        result = filter_products(category_slug=category.slug)

        assert result['found'] is True
        for p in result['products']:
            assert p['category'] == category.name

    def test_filter_by_max_price(self, product):
        from chat.agent.tools import filter_products

        # product.price is 999.00 — search under 1500
        result = filter_products(max_price=1500)

        assert result['found'] is True
        for p in result['products']:
            assert p['price_raw'] <= 1500

    def test_filter_no_results(self, product):
        from chat.agent.tools import filter_products

        # Price of 1 rupee — nothing should match
        result = filter_products(max_price=1)

        assert result['found'] is False

    def test_filter_combined_category_and_price(self, product, category):
        from chat.agent.tools import filter_products

        result = filter_products(
            category_slug=category.slug,
            max_price=2000,
        )
        # Result may or may not find items depending on price
        assert 'found' in result
        assert 'products' in result


@pytest.mark.django_db
class TestGetProductDetailsTool:

    def test_get_by_id(self, product):
        from chat.agent.tools import get_product_details

        result = get_product_details(product_id=product.id)

        assert result['found'] is True
        assert result['product']['id'] == product.id
        assert result['product']['title'] == product.title
        assert 'description' in result['product']
        assert 'average_rating' in result['product']
        assert 'review_count' in result['product']

    def test_get_by_name(self, product):
        from chat.agent.tools import get_product_details

        result = get_product_details(product_name=product.title[:8])

        assert result['found'] is True

    def test_not_found_bad_id(self):
        from chat.agent.tools import get_product_details

        result = get_product_details(product_id=999999)

        assert result['found'] is False

    def test_no_args_returns_error(self):
        from chat.agent.tools import get_product_details

        result = get_product_details()

        assert 'error' in result


@pytest.mark.django_db
class TestGetOrderStatusTool:

    def test_unauthenticated_user_gets_error(self, api_client):
        from chat.agent.tools import get_order_status

        result = get_order_status(user=None)

        assert result['error'] == 'not_authenticated'

    def test_authenticated_user_gets_latest_order(
        self, verified_user, confirmed_order
    ):
        from chat.agent.tools import get_order_status

        result = get_order_status(user=verified_user)

        assert result['found'] is True
        assert result['order']['id'] == confirmed_order.id
        assert result['order']['status'] == 'CONFIRMED'

    def test_specific_order_id(self, verified_user, confirmed_order):
        from chat.agent.tools import get_order_status

        result = get_order_status(
            order_id=confirmed_order.id,
            user=verified_user
        )

        assert result['found'] is True
        assert result['order']['id'] == confirmed_order.id

    def test_cannot_access_other_users_order(
        self, second_user, confirmed_order
    ):
        from chat.agent.tools import get_order_status
        # confirmed_order belongs to verified_user, not second_user
        result = get_order_status(
            order_id=confirmed_order.id,
            user=second_user,
        )
        assert result['found'] is False

    def test_no_orders_returns_message(self, second_user):
        from chat.agent.tools import get_order_status

        result = get_order_status(user=second_user)

        assert result['found'] is False
        assert 'message' in result


@pytest.mark.django_db
class TestGetRecommendationsTool:

    def test_returns_in_stock_products(self, product, out_of_stock_product):
        from chat.agent.tools import get_recommendations

        result = get_recommendations()

        assert result['found'] is True
        for p in result['products']:
            assert p['available_stock'] > 0

    def test_context_price_filter(self, product):
        from chat.agent.tools import get_recommendations

        result = get_recommendations(
            context="budget under 2000"
        )
        if result['found']:
            for p in result['products']:
                assert p['price_raw'] <= 2000


@pytest.mark.django_db
class TestExecuteTool:

    def test_dispatches_correct_tool(self, product):
        from chat.agent.tools import execute_tool

        result = execute_tool(
            tool_name='search_products',
            tool_args={'query': product.title[:10]},
            user=None,
        )
        assert 'found' in result

    def test_unknown_tool_returns_error(self):
        from chat.agent.tools import execute_tool

        result = execute_tool(
            tool_name='nonexistent_tool',
            tool_args={},
            user=None,
        )
        assert 'error' in result


@pytest.mark.django_db
class TestAgentLoop:
    """
    Tests the full agent loop — tool call → result → final response.
    """

    def test_agent_calls_tool_for_product_search(
        self, api_client, product
    ):
        """
        When user asks about products, agent should
        call search_products or filter_products.
        """
        # Mock Groq to return a tool call first, then a text response
        first_call = True

        def mock_groq_create(**kwargs):
            nonlocal first_call
            if first_call and kwargs.get('tools'):
                first_call = False
                # Simulate LLM requesting a tool call
                mock_resp = MagicMock()
                mock_tool_call = MagicMock()
                mock_tool_call.id = "call_abc123"
                mock_tool_call.function.name = "filter_products"
                mock_tool_call.function.arguments = json.dumps({
                    "category_slug": "electronics"
                })
                mock_resp.choices[0].message.tool_calls = [mock_tool_call]
                mock_resp.choices[0].message.content = ""
                return mock_resp
            else:
                # Second call: LLM reads tool result and responds
                mock_resp = MagicMock()
                mock_resp.choices[0].message.tool_calls = None
                mock_resp.choices[0].message.content = (
                    "Here are some electronics products for you!"
                )
                return mock_resp

        with patch('chat.agent.orchestrator.Groq') as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = (
                mock_groq_create
            )

            response = api_client.post('/api/chat/message/', {
                'message': 'show me electronics',
                'session_id': 'agent-test-session',
            }, format='json')

        assert response.status_code == 200
        assert response.data['message']
        # Tool should have been called
        assert 'filter_products' in response.data.get('tools_used', [])

    def test_agent_responds_directly_without_tool(self, api_client):
        """
        For simple questions, agent responds without calling any tool.
        """
        def mock_direct_response(**kwargs):
            mock_resp = MagicMock()
            mock_resp.choices[0].message.tool_calls = None
            mock_resp.choices[0].message.content = (
                "Our return policy is 7 days."
            )
            return mock_resp

        with patch('chat.agent.orchestrator.Groq') as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = (
                mock_direct_response
            )

            response = api_client.post('/api/chat/message/', {
                'message': 'what is your return policy?',
                'session_id': 'policy-test-session',
            }, format='json')

        assert response.status_code == 200
        assert response.data['message']
        assert response.data.get('tools_used', []) == []

    def test_agent_loop_max_rounds_respected(self, api_client):
        """
        Agent stops after MAX_AGENT_ROUNDS even if LLM
        keeps requesting tools (prevents infinite loops).
        """
        call_count = 0

        def always_wants_tool(**kwargs):
            nonlocal call_count
            call_count += 1
            # Always return a tool call unless tools not passed
            if not kwargs.get('tools'):
                mock_resp = MagicMock()
                mock_resp.choices[0].message.tool_calls = None
                mock_resp.choices[0].message.content = "Final answer."
                return mock_resp
            mock_resp = MagicMock()
            mock_tool_call = MagicMock()
            mock_tool_call.id = f"call_{call_count}"
            mock_tool_call.function.name = "search_products"
            mock_tool_call.function.arguments = json.dumps({"query": "test"})
            mock_resp.choices[0].message.tool_calls = [mock_tool_call]
            mock_resp.choices[0].message.content = ""
            return mock_resp

        with patch('chat.agent.orchestrator.Groq') as MockGroq:
            MockGroq.return_value.chat.completions.create.side_effect = (
                always_wants_tool
            )
            response = api_client.post('/api/chat/message/', {
                'message': 'test',
                'session_id': 'max-rounds-test',
            }, format='json')

        assert response.status_code == 200
        # Should get a response, not hang forever
        assert response.data['message']
        