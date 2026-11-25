"""
Tool definitions in Groq's function-calling format.

These are sent to the LLM alongside every message.
The LLM reads them and decides WHICH tool (if any) to call
based on the user's message — we never hardcode the decision.

Design principles:
  - Description must be specific enough that LLM picks the RIGHT tool
  - Parameters must be typed and described clearly
  - required[] lists only truly mandatory params
  - Optional params give the LLM flexibility
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search for products by name, keywords, or description. "
                "Use when the user asks about a specific product by name, "
                "or describes what they're looking for. "
                "Example triggers: 'do you have Sony headphones', "
                "'looking for a backpack', 'show me wireless earbuds'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query — product name or description. "
                            "E.g. 'wireless earbuds', 'leather jacket', "
                            "'gold ring'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Default 4.",
                        "default": 4,
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "filter_products",
            "description": (
                "Filter products by category, price range, or stock status. "
                "Use when the user wants to browse by type or has budget constraints. "
                "Example triggers: 'show me electronics', 'products under 500 rupees', "
                "'what jewellery do you have', 'items in stock under 1000'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category_slug": {
                        "type": "string",
                        "description": (
                            "Category slug to filter by. "
                            "Valid values: 'electronics', 'mens-clothing', "
                            "'womens-clothing', 'jewellery'. "
                            "Omit to search all categories."
                        ),
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price in INR (₹). E.g. 500, 1000, 2000.",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum price in INR (₹).",
                    },
                    "in_stock_only": {
                        "type": "boolean",
                        "description": "If true, only return products with available stock.",
                        "default": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results. Default 5.",
                        "default": 5,
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Get full details of a specific product by its ID or exact name. "
                "Use when the user asks about a specific product they've already seen "
                "or when you need price/stock/review details for a known product. "
                "Example triggers: 'tell me more about that backpack', "
                "'how many are left in stock', 'what's the rating on that jacket'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID if known.",
                    },
                    "product_name": {
                        "type": "string",
                        "description": "Exact or partial product name if ID unknown.",
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Check the status and tracking of a user's order. "
                "ONLY call this for authenticated users. "
                "Example triggers: 'where is my order', 'track my package', "
                "'what's the status of order 42', 'has my order shipped'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": (
                            "Specific order ID if mentioned by user. "
                            "Omit to get their most recent order."
                        ),
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": (
                "Get personalised product recommendations based on user preferences, "
                "browsing context, and what's popular. "
                "Use when the user asks for suggestions without specific criteria, "
                "or when their long-term memory suggests interests. "
                "Example triggers: 'what do you recommend', 'surprise me', "
                "'what's popular', 'what should I buy for a gift'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": (
                            "Any preference context from the conversation. "
                            "E.g. 'budget under 1000, interested in electronics'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of recommendations. Default 4.",
                        "default": 4,
                    },
                },
                "required": [],
            },
        },
    },
]
