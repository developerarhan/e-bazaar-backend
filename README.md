# e-Bazaar — AI-Powered E-Commerce Platform

A modern, full-stack e-commerce shopping platform featuring an autonomous **Agentic AI Shopping Assistant ("Zara")** powered by **`openai/gpt-oss-20b`** on **Groq**, **pgvector on Neon PostgreSQL**, **Django REST Framework**, and **React**.

---

## Architecture Overview

```mermaid
flowchart TD
    Client([React Frontend / Client App]) <-->|REST API + HttpOnly Cookies| Django[Django REST Framework Backend]

    subgraph CoreCommerce [Core E-Commerce Modules]
        Auth[accounts / JWT Cookie Auth & Google OAuth2]
        Catalog[store / Catalog, Inventory & Reviews]
        Orders[orders / Checkout, Razorpay & Tracking]
    end

    subgraph AIAssistant [Agentic AI Assistant — Zara]
        Orchestrator[ChatOrchestrator / Multi-Turn Loop]
        GroqLLM[Groq LPU / openai/gpt-oss-20b]
        ToolEngine[Autonomous Tool Engine / 5 Live Tools]
        RAGPipeline[Semantic RAG / Cosine Similarity]
    end

    subgraph DataStorage [Data & Memory Layer]
        NeonDB[(Neon Postgres + pgvector)]
        RedisCache[(Redis Cache & Message Broker)]
    end

    subgraph BackgroundProcessing [Asynchronous Tasks]
        Worker[Celery Worker / Emails & Cleanup]
        Beat[Celery Beat / Periodic Order Expiration]
    end

    Django --> CoreCommerce
    Django --> AIAssistant

    Catalog <-->|Atomic F Expressions| NeonDB
    Orders <-->|Payment Verification & Tracking| NeonDB
    Auth <-->|User Profiles & JWT Blacklist| NeonDB

    AIAssistant --> Orchestrator
    Orchestrator <--> GroqLLM
    Orchestrator <--> ToolEngine
    Orchestrator <--> RAGPipeline

    ToolEngine --> Catalog
    ToolEngine --> Orders

    RAGPipeline <-->|all-MiniLM-L6-v2 384d Vectors| NeonDB
    Orchestrator <-->|Short-Term History / 2h TTL| RedisCache
    Orchestrator <-->|Long-Term Facts / UserMemory| NeonDB

    Worker <--> RedisCache
    Beat <--> RedisCache
```

---

## Key Features

### 1. Autonomous AI Shopping Assistant ("Zara")
* **LLM Engine**: Powered by **`openai/gpt-oss-20b`** running on Groq's high-speed inference engine (LPU) for low-latency conversational commerce.
* **Autonomous Multi-Turn Tool Calling**: The model reads customer intent, autonomously decides which tools to execute, processes the live results, and synthesizes natural responses (up to 3 agent rounds).
* **Semantic RAG Pipeline**:
  * Dense 384-dimensional vector embeddings generated using `sentence-transformers/all-MiniLM-L6-v2`.
  * Cosine similarity retrieval on Neon PostgreSQL via `pgvector` with native SQL distance operators (`1 - (embedding::vector <=> query::vector) > 0.25`).
  * Real-time vector store re-indexing via Django `post_save` and `post_delete` signals on product catalog changes.
  * Vector index contains products, store policies, and FAQ knowledge bases (`EmbeddingDocument`).
* **5 Live Autonomous Tools**:
  * `search_products`: Keyword and multi-term `Q` lookup across product titles and descriptions.
  * `filter_products`: Parametric filtering by category slug, budget limits (min/max price), and in-stock availability.
  * `get_product_details`: Live product inspector providing stock status, descriptions, review counts, and average ratings.
  * `get_order_status`: Auth-gated tool retrieving live order tracking status and fulfillment timeline.
  * `get_recommendations`: Intelligent recommendation engine with PostgreSQL `Coalesce` review score aggregation.
* **Two-Tier Memory System**:
  * **Short-Term Memory**: In-memory conversational sliding window (last 20 messages) cached in Redis (`chat:history:<session_id>`) with a 2-hour sliding TTL.
  * **Long-Term Memory**: Periodic LLM extraction saving persistent customer facts (budget preferences, interests, sizes) to PostgreSQL `UserMemory` with key whitelisting and prompt-injection defenses.

### 2. Store Catalog & Inventory
* Structured product catalog with categories, image assets, descriptions, and dynamic pricing.
* **Atomic Inventory Reservation**: Concurrency-safe stock reservation using SQL `F()` expressions (`stock__gte=F('reserved_stock') + quantity`) to prevent checkout race conditions.
* Real-time stock status computation (`in_stock`, `low_stock`, `out_of_stock`).
* Customer review system with 1–5 star ratings and relational aggregations.

### 3. Orders, Checkout & Payments
* **Razorpay Payment Integration**: Server-side order creation, cryptographic webhook signature verification, and stock confirmation upon payment success.
* **Fulfillment Tracking**: Step-by-step order tracking timeline (`PENDING_PAYMENT`, `CONFIRMED`, `SHIPPED`, `DELIVERED`, `CANCELLED`) with timestamps.
* **Automated Order Expiration**: Background Celery Beat scheduler releases reserved inventory for abandoned pending orders.

### 4. Authentication & Security
* **JWT Cookie Authentication**: Secure, HttpOnly, `SameSite=None` cookies with access token rotation and refresh token blacklisting.
* **Google OAuth2**: Seamless social login flow via `social-auth-app-django`.
* **Prompt Injection Defenses**: Boundary delimiters, strict persona lock, policy immutability, and memory key validation in the AI agent.

---

## Tech Stack

| Domain | Technology |
| :--- | :--- |
| **Backend Framework** | Django 5.x, Django REST Framework |
| **LLM Model** | **`openai/gpt-oss-20b`** (via Groq Cloud) |
| **Vector Database & RAG** | Neon PostgreSQL with `pgvector` extension |
| **Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`), PyTorch (CPU) |
| **In-Memory Cache & Broker** | Redis (`django-redis`, Celery Broker & Backend) |
| **Task Queue & Scheduler** | Celery, Celery Beat (`django-celery-beat`, `django-celery-results`) |
| **Payment Gateway** | Razorpay Python SDK |
| **Email Delivery** | Anymail with Brevo HTTP API |
| **Authentication** | SimpleJWT (HttpOnly cookies), Google OAuth2 |
| **Production Server** | Gunicorn (threaded mode), WhiteNoise |

---

## Project Structure

```
e-bazaar-backend/
├── accounts/                  # User accounts, JWT cookie auth, Google OAuth2, validators
├── store/                     # Product catalog, categories, reviews, inventory reservation
├── orders/                    # Orders, line items, order tracking, Razorpay integration
├── chat/                      # Agentic AI shopping assistant (Zara)
│   ├── agent/
│   │   ├── memory.py          # Short-term (Redis) & Long-term (Postgres) memory systems
│   │   ├── orchestrator.py    # Agent loop with openai/gpt-oss-20b & tool dispatcher
│   │   ├── prompts.py         # System prompt, security guardrails & extraction prompts
│   │   ├── rag.py             # pgvector cosine similarity search & context formatting
│   │   ├── tool_definitions.py# OpenAI/Groq function-calling schemas
│   │   └── tools.py           # 5 live autonomous tool implementations
│   ├── embeddings/
│   │   ├── encoder.py         # SentenceTransformer singleton wrapper (384d)
│   │   ├── pipeline.py        # Product/FAQ/Policy batch and single embedding pipelines
│   │   └── static_content.py  # FAQ and store policy static knowledge base
│   ├── management/commands/
│   │   └── embed_products.py  # CLI command to build/rebuild the vector store
│   ├── models.py              # ChatConversation, UserMemory, EmbeddingDocument
│   ├── signals.py             # Auto-reindexing hooks on product save/delete
│   └── views.py               # REST API endpoints for chat, history, and clear
├── ebazaar/                   # Core Django project configuration
│   ├── settings/
│   │   ├── base.py            # Common configuration, logging, and AI defaults
│   │   ├── development.py     # Local development settings
│   │   └── production.py      # Hardened production settings (SSL, CORS, Cookies, Neon)
│   ├── celery.py              # Celery task configuration
│   ├── urls.py                # Global URL routing
│   └── wsgi.py                # WSGI entrypoint
├── Dockerfile                 # Multi-stage production container
├── run.sh                     # Production startup script (Gunicorn + Celery)
└── requirements.txt           # Python package dependencies
```

---

## Environment Variables

Configure these environment variables in your `.env` file or deployment dashboard:

```env
# Django Core
SECRET_KEY=your-django-secret-key
DJANGO_SETTINGS_MODULE=ebazaar.settings.production
ALLOWED_HOST=your-backend.onrender.com
FRONTEND_URL=https://your-frontend.vercel.app

# Database (Neon PostgreSQL with pgvector)
DATABASE_URL=postgresql://user:password@ep-xyz.us-east-1.aws.neon.tech/neondb?sslmode=require

# Redis & Celery
REDIS_URL=redis://your-redis-host:6379

# Groq AI & Model Configuration
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

# Payment Gateway (Razorpay)
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...

# Google OAuth2
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-frontend.vercel.app/oauth/google/callback

# Email Service (Brevo / Anymail)
BREVO_API_KEY=xkeysib-...
DEFAULT_FROM_EMAIL=support@e-bazaar.com
```

---

## Local Development Setup

### 1. Prerequisites
* Python 3.12+
* Redis server running locally or via Docker
* PostgreSQL with `pgvector` extension (or a free cloud database on Neon)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/e-bazaar-backend.git
cd e-bazaar-backend

# Create virtual environment
python -m venv env

# Activate environment
# On Windows:
.\env\Scripts\activate
# On Linux / macOS:
source env/bin/activate

# Install CPU PyTorch first (avoids heavy CUDA GPU packages)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
pip install -r requirements.txt
```

### 3. Database & pgvector Setup
In your PostgreSQL / Neon SQL editor, enable the vector extension:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Run database migrations:
```bash
python manage.py migrate
```

### 4. Build Vector Store Embeddings
Seed the RAG vector store with embeddings for all existing products, store policies, and FAQs:
```bash
python manage.py embed_products
```

Additional CLI options:
```bash
python manage.py embed_products --type product   # Embed products only
python manage.py embed_products --type faq       # Embed FAQs only
python manage.py embed_products --type policy    # Embed policies only
python manage.py embed_products --clear          # Wipe and rebuild entire vector store
```

### 5. Running the Application
```bash
# Terminal 1: Run Django REST API
python manage.py runserver

# Terminal 2: Run Celery Worker
celery -A ebazaar worker --loglevel=info --pool=solo

# Terminal 3: Run Celery Beat Scheduler
celery -A ebazaar beat --loglevel=info
```

---

## Production Deployment (Render & Neon)

### Neon PostgreSQL Configuration
1. Open the **SQL Editor** on [Neon](https://neon.tech).
2. Run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Set your `DATABASE_URL` in Render environment variables with `sslmode=require`.

### Render Free Tier Optimization (512MB RAM)
In [`run.sh`](run.sh), Gunicorn is configured in single-worker threaded mode:
```bash
gunicorn ebazaar.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 2 \
    --timeout 120
```
*Loading PyTorch and `all-MiniLM-L6-v2` in a single multi-threaded process keeps memory consumption around ~300MB, preventing OOM terminations on Render's 512MB free tier.*

### Seeding Embeddings on Render Free Tier
Because interactive shell access is disabled on Render Free Tier, run the embedding script **from your local machine pointing to Neon**:
```bash
# With your local .env DATABASE_URL pointing to Neon:
python manage.py embed_products
```
*Your local CPU/RAM generates the embeddings and writes them directly to Neon PostgreSQL, eliminating memory usage and shell requirements on Render.*

---

## REST API Reference

### AI Shopping Assistant ("Zara")
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/chat/message/` | `POST` | Send message to Zara; returns response, session ID, and RAG sources |
| `/api/chat/history/?session_id=<id>` | `GET` | Fetch Redis session conversation history |
| `/api/chat/clear/` | `POST` | Clear short-term history while preserving long-term preferences |

### Store & Catalog
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/store/products/` | `GET` | List paginated products with search & category filters |
| `/api/store/products/<id>/` | `GET` | Retrieve product details, ratings, and stock status |
| `/api/store/categories/` | `GET` | List all product categories |
| `/api/store/products/<id>/reviews/` | `POST` | Submit a product review and rating |

### Orders & Checkout
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/orders/create/` | `POST` | Create a pending order and atomically reserve stock |
| `/api/orders/verify-payment/` | `POST` | Verify Razorpay payment signature & confirm stock deduction |
| `/api/orders/<id>/` | `GET` | Fetch order details, line items, and fulfillment tracking history |

### Authentication & Accounts
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/accounts/register/` | `POST` | Register a new customer account |
| `/api/accounts/login/` | `POST` | Login user and issue HttpOnly JWT cookies |
| `/api/accounts/logout/` | `POST` | Clear auth cookies and blacklist refresh token |
| `/api/accounts/refresh/` | `POST` | Refresh access token via HttpOnly cookie |
| `/api/accounts/google/` | `GET` | Initiate Google OAuth2 login flow |

---

## License

This project is licensed under the [MIT License](LICENSE).
