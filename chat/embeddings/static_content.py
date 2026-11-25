"""
Static content that gets embedded into pgvector.
 
These are  store's FAQs and policies.
Update these as store policies change.
 
Format for each entry:
  {
    "question": "...",   ← used as the embeddable text
    "answer": "...",     ← returned to LLM as context
    "tags": ["..."],     ← for metadata filtering (future)
  }
"""

FAQS = [
    {
        "question": "What is the return policy?",
        "answer": (
            "e-Bazaar offers a 7-day return policy on all products. "
            "Items must be in original condition with tags attached. "
            "To initiate a return, contact our support team via chat "
            "or email. Refunds are processed within 5-7 business days "
            "after we receive the returned item."
        ),
        "tags": ["returns", "refund", "policy"],
    },
     {
        "question": "How long does delivery take?",
        "answer": (
            "Standard delivery takes 3-7 business days depending on "
            "your location. Metro cities (Mumbai, Delhi, Bangalore, "
            "Chennai, Hyderabad, Pune) typically receive orders in "
            "3-4 days. Other cities and towns take 5-7 days. "
            "Express delivery is not currently available."
        ),
        "tags": ["delivery", "shipping", "timeline"],
    },
    {
        "question": "What are the delivery charges?",
        "answer": (
            "Delivery is FREE on all orders above ₹500. "
            "For orders below ₹500, a flat delivery charge of ₹50 applies. "
            "The delivery charge is calculated and shown at checkout."
        ),
        "tags": ["delivery", "shipping", "charges", "free delivery"],
    },
    {
        "question": "What payment methods do you accept?",
        "answer": (
            "We accept all major payment methods via Razorpay: "
            "UPI (GPay, PhonePe, Paytm, BHIM), Credit/Debit Cards "
            "(Visa, Mastercard, RuPay, Amex), Net Banking (all major banks), "
            "and Digital Wallets. All payments are secure and encrypted."
        ),
        "tags": ["payment", "upi", "card", "razorpay"],
    },
    {
        "question": "How do I track my order?",
        "answer": (
            "You can track your order in the 'My Orders' section after "
            "logging in. Each order shows its current status: "
            "Pending Payment → Confirmed → Shipped → Delivered. "
            "You'll also receive email notifications at each stage. "
            "If you need more details, share your order ID in this chat."
        ),
        "tags": ["tracking", "order", "status", "shipment"],
    },
    {
        "question": "Can I cancel my order?",
        "answer": (
            "Orders can be cancelled before they are shipped. "
            "Once an order is in 'Shipped' status, cancellation is "
            "not possible — you'll need to wait for delivery and "
            "then initiate a return. To cancel, go to My Orders → "
            "select the order → Cancel Order, or contact us via chat."
        ),
        "tags": ["cancel", "cancellation", "order"],
    },
    {
        "question": "Is cash on delivery available?",
        "answer": (
            "Currently we do not offer Cash on Delivery (COD). "
            "All payments must be made online via Razorpay at the "
            "time of placing the order. We accept UPI, cards, "
            "net banking and wallets."
        ),
        "tags": ["cod", "cash on delivery", "payment"],
    },
    {
        "question": "How do I create an account?",
        "answer": (
            "Click 'Register' in the top navigation. Enter your name, "
            "email and a strong password. You'll receive a verification "
            "email — click the link to activate your account. "
            "You can also sign up instantly using Google Login "
            "by clicking 'Continue with Google'."
        ),
        "tags": ["account", "register", "signup", "google"],
    },
    {
        "question": "I forgot my password, how do I reset it?",
        "answer": (
            "Click 'Login', then 'Forgot Password?' below the login form. "
            "Enter your registered email address and we'll send you a "
            "password reset link. The link is valid for 1 hour. "
            "Note: If you signed up with Google, you cannot reset a "
            "password — just use 'Continue with Google' to log in."
        ),
        "tags": ["password", "forgot", "reset", "login"],
    },
    {
        "question": "Are the products genuine and authentic?",
        "answer": (
            "Yes, all products on e-Bazaar are genuine and sourced from "
            "verified suppliers. Products come with manufacturer warranty "
            "where applicable. Customer reviews with 'Verified Purchase' "
            "badges are from users who actually bought the product, "
            "giving you authentic feedback."
        ),
        "tags": ["genuine", "authentic", "quality", "warranty"],
    },
    {
        "question": "How do I write a product review?",
        "answer": (
            "Go to the product page and scroll down to the Reviews section. "
            "Click 'Write a Review', select your star rating (1-5 stars), "
            "and write your experience. You must be logged in to leave a review. "
            "Reviews from users who purchased the product are marked as "
            "'Verified Purchase' automatically."
        ),
        "tags": ["review", "rating", "feedback"],
    },
    {
        "question": "What categories of products do you sell?",
        "answer": (
            "e-Bazaar currently sells products in four categories: "
            "Electronics (headphones, accessories, gadgets), "
            "Men's Clothing (shirts, jackets, casual wear), "
            "Women's Clothing (dresses, tops, ethnic wear), and "
            "Jewellery (rings, necklaces, earrings). "
            "We're regularly adding new products."
        ),
        "tags": ["categories", "products", "electronics", "clothing", "jewellery"],
    },
]

POLICIES = [
    {
        "title": "Shipping Policy",
        "content": (
            "e-Bazaar ships across India. Standard delivery is 3-7 business days. "
            "Orders above ₹500 get free shipping; below ₹500 a ₹50 charge applies. "
            "We use reputed courier partners for all deliveries. "
            "Tracking information is provided once the order is shipped."
        ),
        "tags": ["shipping", "delivery"],
    },
    {
        "title": "Return and Refund Policy",
        "content": (
            "7-day returns accepted for all products in original condition. "
            "Items must have original packaging and tags. "
            "Damaged, used, or altered products are not eligible for return. "
            "Refunds go back to the original payment method within 5-7 business days. "
            "For defective products, we offer free replacement or full refund."
        ),
        "tags": ["returns", "refund", "damaged"],
    },
    {
        "title": "Privacy Policy Summary",
        "content": (
            "e-Bazaar collects only necessary information: name, email, "
            "phone, and delivery address for order fulfillment. "
            "We never sell your personal data to third parties. "
            "Payment information is handled entirely by Razorpay — "
            "we never store card numbers or UPI details. "
            "You can request deletion of your account at any time."
        ),
        "tags": ["privacy", "data", "security"],
    },
]
 