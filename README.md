# 💊 AI Explorer Pharmacy

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.57-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![OpenAI](https://img.shields.io/badge/OpenAI_GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![AWS](https://img.shields.io/badge/AWS-EC2_|_ECR_|_SES-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)

An AI-powered pharmacy assistant that combines natural language understanding with real-time database access. Customers can ask health questions, get product recommendations, identify medications from photos, place orders through conversation, and receive PDF invoices via email — all in a single chat interface. Built from scratch with Python, Streamlit, OpenAI GPT-4o-mini, and PostgreSQL, deployed on AWS.

> 🚀 **Live demo:** [http://44.220.247.80](http://44.220.247.80)

> 🔐 **Credentials:** `david@pharmacy.com` / `123456`

> 👤 **Author:** [David Pedroza Sánchez](https://www.linkedin.com/in/david-pedroza-sanchez-9525b0346)

---

## 📸 Preview
 
<!-- Add your screenshots here -->
| Welcome Screen | Chat Interface |
|---|---|
| <img width="1030" height="523" alt="image" src="https://github.com/user-attachments/assets/6c60d374-6769-4872-aa37-f85a3121df37" /> | <img width="840" height="792" alt="Screenshot 2026-06-03 173344" src="https://github.com/user-attachments/assets/02038122-0a1a-4c79-bd31-01de249bc7a8" />|
 
| SQL Query + Results | Data Visualization |
|---|---|
| <img width="760" height="395" alt="image" src="https://github.com/user-attachments/assets/7ef7e972-ef74-46d0-a851-d36bf3d14f09" />| <img width="756" height="412" alt="image" src="https://github.com/user-attachments/assets/16bae06b-9dca-4a35-8f86-695e3b2f73dd" />|
 
| Image Analysis | Order + PDF | 
|---|---|
| <img width="830" height="889" alt="image" src="https://github.com/user-attachments/assets/0e7f92ea-e0c8-4f5a-bf6a-9eb53c728851" />| `[screenshot-pdf.png]` |
 
| Conversation History | Email Delivery |
|---|---|
| `[screenshot-sidebar.png]` | `[screenshot-email.png]` |
 
---

## ✨ Features

### 🤖 AI-Powered Chat
- **Natural language SQL generation** — Ask questions like "top 5 selling products" and the AI generates, validates, and executes PostgreSQL queries in real time
- **Conversational health advice** — Medical recommendations, drug interactions, and symptom-based suggestions powered by GPT-4o-mini
- **Intent classification** — Automatically routes questions to database queries or conversational responses
- **Context-aware responses** — Maintains conversation history so follow-up questions like "how much does it cost?" resolve correctly

### 📊 Automatic Data Visualization
- **Smart chart classification** — AI determines if results need a Bar, Line, or Pie chart
- **Interactive Plotly charts** — Rendered inline alongside query results
- **Data tables** — Full result sets displayed in expandable dataframes

### 📷 Medication Image Recognition
- **Single image analysis** — Upload a photo of any medication packaging and get instant identification + pharmacy stock recommendations
- **Multi-image support** — Upload up to 15 medication images at once for bulk identification
- **OpenAI Vision integration** — Extracts drug name, dosage, form, and laboratory from packaging images
- **Automatic product matching** — Fuzzy-matches identified medications against the pharmacy database using PostgreSQL pg_trgm

### 🛒 Complete Order Flow
- **Single-product orders** — Conversational ordering with product selection, data collection, and confirmation
- **Multi-product orders** — Order multiple medications in one flow, with intelligent handling of multiple presentations/laboratories
- **PDF invoice generation** — Professional invoices with customer data, product details, and branding (supports Spanish, English, French)
- **Email delivery via AWS SES** — Invoices sent automatically as PDF attachments with HTML-formatted email bodies
- **Order persistence** — Orders saved to PostgreSQL with status tracking and history

### 🔐 Authentication & Sessions
- **User registration and login** — Secure password hashing with PBKDF2-SHA256
- **Cookie-based session persistence** — Stay logged in across browser sessions (30-day expiry)
- **Conversation history** — All chats saved and reloadable from the sidebar
- **Guest mode** — Full functionality without login (conversations not persisted)

### 🌐 Multilingual
- **Automatic language detection** — Responds in the same language the customer uses (Spanish, English, French)
- **Multilingual invoices** — PDF content adapts to the conversation language
- **Multilingual emails** — Email body generated in the detected language

### 🎨 Professional UI
- **Custom CSS layout** — Pinned input bar, gradient welcome screen, responsive design
- **Sidebar with conversation history** — Quick access to previous chats with user avatar section
- **Image upload with preview** — Clip button for attaching medication photos with thumbnails
- **Suggestion chips** — Quick-start buttons for common queries on the welcome screen

---

## 🧱 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Streamlit 1.57 | Chat UI, file uploads, data visualization |
| AI Engine | OpenAI GPT-4o-mini | SQL generation, intent classification, image analysis, NLP |
| Database | PostgreSQL 18 | Product catalog, orders, users, conversations |
| Fuzzy Search | pg_trgm extension | Typo-tolerant product matching across languages |
| Charts | Plotly 6.7 | Interactive bar, line, and pie charts |
| PDF Generation | fpdf2 2.8 | Professional invoice PDFs with multilingual support |
| Email | AWS SES + boto3 | Invoice delivery with HTML body + PDF attachment |
| Auth | PBKDF2-SHA256 + cookies | Secure password hashing and session management |
| Containerization | Docker + Docker Compose | Multi-service orchestration |
| Infrastructure | AWS EC2 + ECR | Deployment and private container registry |

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    AWS EC2 (t3.small)                         │
│                    Ubuntu 26.04 LTS                           │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Docker Compose                             │  │
│  │                                                         │  │
│  │  ┌──────────────┐  ┌────────────┐  ┌──────────────┐     │  │
│  │  │  Streamlit   │  │ PostgreSQL │  │    Seeder    │     │  │
│  │  │  GPT-4o-mini │  │   :5432    │  │  (run once)  │     │  │
│  │  │    :80       │──│  pg_trgm   │──│  Faker data  │     │  │
│  │  └──────────────┘  └────────────┘  └──────────────┘     │  │
│  │         │                                               │  │
│  │         ├── OpenAI API (SQL gen, vision, NLP)           │  │
│  │         └── AWS SES (invoice emails)                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
         ↑ HTTP :80
         │
    ┌────┴───────────────────────────────┐
    │      Amazon ECR (private)          │
    │      ai-explorer/app:latest        │
    │      ai-explorer/seeder:latest     │
    └────────────────────────────────────┘
```

---

## 🧠 How the AI Works

```
User Input
    │
    ├─── Has image attached? ──→ OpenAI Vision ──→ Identify medication ──→ Fuzzy DB search ──→ Recommend
    │
    ├─── Order flow active? ──→ State machine (selection → data → confirm → PDF → email)
    │
    └─── Text only?
              │
              ├── classify_intent() ──→ "CONVERSATIONAL" ──→ Health advice + product recommendations
              │
              └── classify_intent() ──→ "DATABASE" ──→ extract_product_term()
                                                            │
                                                            ├── find_matching_products() (pg_trgm fuzzy)
                                                            │
                                                            ├── generate_sql() ──→ validate_sql() ──→ execute
                                                            │
                                                            ├── classify_chart_type() ──→ render Plotly chart
                                                            │
                                                            └── summarize_query_results() ──→ natural language response
```

---

## 📂 Project Structure

```
AI_Explorer/
├── app/
│   ├── main.py                    # Streamlit entry point, session state, routing
│   ├── chat_handlers.py           # Message processing, image handling, DB queries
│   ├── order_handlers.py          # Single-product order flow (selection → invoice)
│   ├── multi_order_handlers.py    # Multi-product order flow
│   ├── ui_components.py           # CSS injection, sidebar, welcome screen, charts
│   └── services/
│       ├── ai_service.py          # Core AI functions (intent, SQL, summarization)
│       ├── ai_image_service.py    # OpenAI Vision — single and multi-image analysis
│       ├── ai_order_service.py    # Order extraction, data parsing, confirmations
│       ├── ai_prompts.py          # All system prompts and DDL constants
│       ├── key_manager.py         # OpenAI client initialization
│       ├── db_service.py          # PostgreSQL connection, queries, fuzzy search
│       ├── auth_service.py        # User auth, conversations, message persistence
│       ├── pdf_service.py         # Invoice PDF generation (multilingual)
│       └── email_service.py       # AWS SES email delivery
├── database/
│   └── init.sql                   # Full schema (12 tables, constraints, indexes)
├── seeder/
│   ├── seeder.py                  # Generates 32 products, 10 customers, 20 orders, conversations
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml             # Local development (build from source)
├── docker-compose.prod.yml        # Production (pull from ECR)
├── Dockerfile                     # Multi-stage Python 3.12 + Streamlit
├── .dockerignore                  # Excludes secrets, venv, cache from images
├── .env.example                   # Template for environment variables
├── requirements.txt               # Python dependencies
└── README.md
```

---

## 🗄️ Database Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  categories  │     │  suppliers   │     │    customers     │
│  id, name    │     │  id, name    │     │  id, name, email │
│  description │     │  email       │     │  address, phone  │
└──────┬───────┘     └──────┬───────┘     └────────┬─────────┘
       │                    │                      │
       └─────────┬──────────┘                      │
                 ▼                                 ▼
       ┌──────────────────┐              ┌──────────────────┐
       │     products     │              │      orders      │
       │  id, name, price │              │  id, total       │
       │  dosage, form    │──────────────│  order_state     │
       │  laboratory      │              │  customers_id    │
       │  category_id     │              └────────┬─────────┘
       │  supplier_id     │                       │
       └────────┬─────────┘              ┌────────┴─────────┐
                │                        │   order_items    │
       ┌────────┴─────────┐              │  products_id     │
       │    inventory     │              │  quantity, price │
       │  actual_stock    │              └──────────────────┘
       │  minimum_stock   │
       └──────────────────┘

       ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
       │    users     │────▶│  conversations   │────▶│   messages  |
       │  id, name    │     │  id, title       │     │  sender      │
       │  email       │     │  user_id         │     │  content     │
       │  password    │     └──────────────────┘     │  images      │
       └──────────────┘                              └──────────────┘
```

12 tables total: `categories`, `suppliers`, `customers`, `products`, `product_images`, `inventory`, `orders`, `order_items`, `order_status_history`, `users`, `conversations`, `messages`

---

## 🚀 Running Locally

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running
- An [OpenAI API key](https://platform.openai.com/api-keys)
- Git

### Launch with Docker Compose

```bash
git clone https://github.com/DPS1031/AI_Explorer.git
cd AI_Explorer

# Create your .env from the template
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (required) and optionally AWS SES credentials

# Start all services
docker compose up --build
```

Docker Compose starts services in the correct dependency order:

1. **PostgreSQL** — waits until healthy (healthcheck)
2. **Seeder** — populates the database with sample data (runs once)
3. **Streamlit** — starts the AI chat interface

| Service | URL |
|---|---|
| 💊 AI Explorer | http://localhost:8501 |

### Without Docker (development)

```bash
# Start PostgreSQL locally (or use Docker for just the DB)
docker compose up postgres -d

# Install Python dependencies
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# Run the seeder
python seeder/seeder.py

# Start the app
streamlit run app/main.py
```

---

## 🔑 Test Credentials

| Email | Password | Role |
|---|---|---|
| `david@pharmacy.com` | `123456` | Test user |
| `maria@pharmacy.com` | `123456` | Test user |
| `carlos@pharmacy.com` | `123456` | Test user |

> ⚠️ These credentials are for development/demo only.

---

## 🌐 Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Required
OPENAI_API_KEY="your_api_key"

# PostgreSQL
POSTGRES_USER=pharmacy_admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=ecommerce
DATABASE_URL=postgresql://user:pass@postgres:5432/ecommerce

# AWS SES (optional — for invoice emails)
AWS_ACCESS_KEY_ID=your_key          # Only needed locally; EC2 uses IAM Role
AWS_SECRET_ACCESS_KEY=your_secret   # Only needed locally; EC2 uses IAM Role
AWS_REGION=us-east-1
SES_SENDER_EMAIL=noreply@yourdomain.com

# App
DEBUG=true
```

> ⚠️ Never commit your real `.env` file. It is listed in `.gitignore`.

---

## ☁️ AWS Deployment

### Services Used

| AWS Service | Purpose |
|---|---|
| EC2 (t3.small) | Hosts Docker Compose (Streamlit + PostgreSQL) |
| ECR | Private container registry for app and seeder images |
| IAM Role | Secure EC2→ECR access + SES permissions (no hardcoded keys) |
| SES | Sends invoice emails with PDF attachments |

### Deployment Workflow

```bash
# 1. Authenticate against ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# 2. Build and push the Streamlit app
docker build -t ai-explorer/app .
docker tag ai-explorer/app:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/app:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/app:latest

# 3. Build and push the seeder
docker build -t ai-explorer/seeder ./seeder
docker tag ai-explorer/seeder:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/seeder:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/seeder:latest

# 4. On the EC2 instance — pull and run
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker pull ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/app:latest
docker pull ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/seeder:latest
docker compose -f docker-compose.prod.yml up -d
```

---

## 🔒 Security

- **IAM Role** attached to EC2 — authenticates against ECR and SES using temporary, auto-rotating credentials. No access keys stored on the server.
- **Private ECR repositories** — Docker images not publicly accessible.
- **PostgreSQL not exposed** — Database port 5432 is internal to the Docker network only, not reachable from the internet.
- **Password hashing** — PBKDF2-SHA256 with 100,000 iterations and random salt per user.
- **SQL validation** — All AI-generated queries pass through `validate_sql()` which blocks INSERT, UPDATE, DELETE, DROP, ALTER, and other dangerous operations before execution.
- **Environment secrets** — All API keys and credentials injected via environment variables, excluded from Docker images via `.dockerignore`.

---

## 🧠 Key Technical Decisions

| Decision | Rationale |
|---|---|
| OpenAI GPT-4o-mini over larger models | Best cost/performance ratio for SQL generation and intent classification. Fast enough for real-time chat. |
| PostgreSQL pg_trgm for fuzzy search | Handles typos and cross-language matching (e.g., "acetaminofen" matches "Acetaminophen") without external search engines. |
| Streamlit over React/Next.js | Rapid prototyping of data-heavy AI applications. Built-in chat components, file uploaders, and session state. Single Python codebase. |
| Docker Compose on EC2 over ECS/Fargate | Simpler for a personal project. Full control, lower cost, no orchestration complexity. PostgreSQL runs alongside the app. |
| fpdf2 over WeasyPrint/ReportLab | Lightweight, no system dependencies, fast PDF generation. Sufficient for structured invoices. |
| Cookie-based sessions over JWT | Simpler for a Streamlit app. No API layer to protect — sessions are server-side with a cookie pointer. |
| State machine for order flow | Complex multi-step process (product selection → data collection → confirmation → PDF → email) cleanly managed through `st.session_state.order_flow` states. |
| Multilingual by AI detection | No i18n library needed. GPT-4o-mini detects the customer's language from conversation history and responds accordingly. |

---

## 📋 Sample Queries You Can Try

| Query | What happens |
|---|---|
| "What's good for a headache?" | Conversational response + product recommendations from DB |
| "Show me top 5 selling products" | SQL generated → bar chart + data table + summary |
| "How much does Ibuprofen cost?" | Product lookup with all presentations and laboratories |
| "Give me a quote for 2 acetaminophen and 3 vitamin C" | Multi-product budget calculation |
| "I want to order that" (after a recommendation) | Enters order flow → asks for personal data → generates invoice |
| 📷 Upload a medication photo + "Do you have this?" | Vision identifies the drug → fuzzy search → shows availability |
| 📷 Upload 5 medication photos + "I need refills" | Multi-image analysis → identifies all → offers to order them |

---

## 📄 License

This project is open source and available for educational and portfolio purposes.

---

<p align="center">
  Built with ❤️ by <a href="https://www.linkedin.com/in/david-pedroza-sanchez-9525b0346">David Pedroza Sánchez</a>
</p>
