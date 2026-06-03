# 💊 AI Explorer — Pharmacy Intelligence Assistant

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.56-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![AWS](https://img.shields.io/badge/AWS-EC2%20%2B%20SES%20%2B%20ECR-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/)

A full-stack AI-powered pharmacy assistant that converts natural language into SQL queries, generates automated data visualizations, processes images with computer vision, and handles complete order workflows with multilingual PDF generation and email delivery via AWS SES.

> 🚀 **Live demo:** [http://44.220.247.80/](http://44.220.247.80/)
> 🔐 **Demo credentials:** `maria@pharmacy.com` / `123456`

---

## 📸 Preview

<!-- Add your screenshots here -->
| Welcome Screen | Chat Interface |
|---|---|
| `[screenshot-welcome.png]` | `[screenshot-chat.png]` |

| SQL Query + Results | Data Visualization |
|---|---|
| `[screenshot-sql.png]` | `[screenshot-chart.png]` |

| Image Analysis | Order + PDF | 
|---|---|
| `[screenshot-vision.png]` | `[screenshot-pdf.png]` |

| Conversation History | Email Delivery |
|---|---|
| `[screenshot-sidebar.png]` | `[screenshot-email.png]` |

---

## ✨ Features

### 🤖 AI Core
- **Natural language → SQL** — GPT-4o-mini generates precise PostgreSQL queries from plain text in any language
- **Conversational responses** — intent classifier routes general medical/pharmaceutical questions to a conversational AI response without hitting the database
- **Computer vision** — analyze up to 15 images simultaneously; GPT-4o-mini identifies medications, reads labels, and cross-references the product catalog
- **Fuzzy search** — `pg_trgm` extension finds products even with typos or cross-language name variations (ibuprofen / ibuprofeno / ibuprofène)

### 📊 Data Visualization
- **Automatic chart classification** — AI decides whether results need a BAR, LINE, PIE chart, or just a table
- **Plotly-powered charts** — interactive, zoomable visualizations rendered inline in the chat
- **Persistent chat history** — every query result with its chart and table persists across the conversation

### 🔐 Authentication
- **Register + Login** — full auth flow with session persistence via cookies
- **Per-user conversation history** — conversations saved to PostgreSQL, loaded on login
- **Sidebar with search** — searchable conversation history, new chat button, session management

### 📦 Order Workflow
- **Single and multi-product orders** — place orders conversationally, with quantity and product confirmation
- **Multilingual PDF generation** — professional invoice in ES / EN / FR depending on the conversation language (ReportLab)
- **AWS SES email delivery** — PDF attached and sent automatically to the customer's email
- **Complete order tracking** — orders, items, and status history persisted to PostgreSQL

### 🌍 Multilingual
- Detects and responds in the user's language automatically (Spanish, English, French)
- PDF invoices generated in the detected language
- Fuzzy product search works across language variants

---

## 🧱 Tech Stack

### Application
| Layer | Technology | Purpose |
|---|---|---|
| Frontend + Backend | Streamlit 1.56 | Single-file Python web app with chat UI |
| AI | OpenAI GPT-4o-mini | SQL generation, conversation, vision, classification |
| Database | PostgreSQL 18 | Pharmacy data, users, orders, conversation history |
| PDF | ReportLab | Multilingual invoice generation |
| Charts | Plotly Express | BAR / LINE / PIE visualizations |
| Auth | Cookie-based sessions | Login persistence across page reloads |
| Fuzzy Search | pg_trgm | Cross-language product matching |

### Infrastructure
| Service | Purpose |
|---|---|
| AWS EC2 (t3.small) | Hosts all Docker containers |
| AWS ECR | Private container registry (app + seeder images) |
| AWS SES | Transactional email with PDF attachments |
| AWS IAM Role | EC2 → ECR + SES access (no hardcoded credentials) |
| Docker Compose | Orchestrates PostgreSQL + Seeder + Streamlit |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                AWS EC2 (t3.small)                   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │            Docker Compose Network            │   │
│  │                                              │   │
│  │  ┌────────────┐   ┌────────────┐            │   │
│  │  │ PostgreSQL │   │  Seeder    │ (one-shot)  │   │
│  │  │   :5432    │   │  (Faker)   │             │   │
│  │  └─────┬──────┘   └────────────┘            │   │
│  │        │                                     │   │
│  │  ┌─────▼──────────────────────────────────┐ │   │
│  │  │         Streamlit App  :8501           │ │   │
│  │  │                                        │ │   │
│  │  │  Intent Classifier → CONVERSATIONAL    │ │   │
│  │  │                    → DATABASE          │ │   │
│  │  │                        ↓               │ │   │
│  │  │  SQL Generator → Executor → Visualizer │ │   │
│  │  │  Vision Analyzer (up to 15 images)     │ │   │
│  │  │  Order Manager → PDF → AWS SES         │ │   │
│  │  └────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                          │
              ┌───────────▼──────────┐
              │   Amazon ECR         │
              │   ai-explorer/app    │
              │   ai-explorer/seeder │
              └──────────────────────┘
                          │
              ┌───────────▼──────────┐
              │   AWS SES            │
              │   PDF email delivery │
              └──────────────────────┘
```

---

## 🗄️ Database Schema

```
categories ──┐
             ├── products ──── product_images
suppliers ───┘       │
                     └──── inventory
                     
customers ──── conversations ──── messages
    │
    └──── orders ──── order_items
              └──── order_status_history
```

11 tables covering the full pharmacy domain — products, inventory, orders, customers, suppliers, and AI conversation history.

---

## 📂 Project Structure

```
AI_Explorer/
├── app/
│   └── main.py              # Streamlit app — all UI and AI logic
├── database/
│   └── init.sql             # PostgreSQL schema (11 tables)
├── seeder/
│   ├── seeder.py            # Faker-based data generation
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml       # Orchestrates 3 services
├── Dockerfile               # Streamlit app image
├── requirements.txt
├── .env.example
└── start.ps1                # Windows helper script (loads .env → Docker)
```

---

## ⚡ Quick Start

### Prerequisites
- Docker Desktop running
- OpenAI API key
- AWS account with SES verified sender (for email features)

### 1. Clone and configure

```bash
git clone https://github.com/DPS1031/AI_Explorer.git
cd AI_Explorer
cp .env.example .env
# Edit .env with your real credentials
```

### 2. Run (Windows)

```powershell
.\start.ps1
```

### 3. Run (Linux / Mac)

```bash
docker compose up --build
```

Open [http://localhost:8501](http://localhost:8501)

Docker Compose starts services in dependency order:

1. **PostgreSQL** — initializes schema from `init.sql`
2. **Seeder** — populates realistic pharmacy data (Faker), then exits
3. **Streamlit** — starts after seeder completes

---

## 🔑 Demo Credentials

| Name | Email | Password |
|---|---|---|
| Maria Garcia | `maria@pharmacy.com` | `123456` |
| Carlos Lopez | `carlos@pharmacy.com` | `123456` |

---

## 🌐 Environment Variables

```env
# OpenAI
OPENAI_API_KEY=your-openai-api-key

# PostgreSQL
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=Pharmacy_db
POSTGRES_HOST=postgres

# AWS
AWS_ACCESS_KEY_ID=your-access-key        # Only for local dev
AWS_SECRET_ACCESS_KEY=your-secret-key    # IAM Role used on EC2
AWS_REGION=us-east-1
AWS_SES_SENDER=verified@yourdomain.com
```

> ⚠️ Never commit your `.env` file. It is listed in `.gitignore`. On EC2, credentials are provided via IAM Role — no keys stored on the server.

---

## ☁️ AWS Deployment

```bash
# 1. Authenticate against ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 2. Build and push app image
docker build -t ai-explorer/app .
docker tag ai-explorer/app:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/app:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/app:latest

# 3. Build and push seeder image
cd seeder
docker build -t ai-explorer/seeder .
docker tag ai-explorer/seeder:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/seeder:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-explorer/seeder:latest

# 4. SSH into EC2 and pull + run
ssh -i your-key.pem ec2-user@44.220.247.80
docker compose up -d
```

---

## 🔒 Security

- **IAM Role** attached to EC2 — temporary, auto-rotating credentials for ECR and SES access. No access keys stored on the server.
- **Cookie-based auth** — sessions validated server-side on every request.
- **SQL injection prevention** — all database queries use parameterized statements via psycopg2. The AI-generated SQL is executed in read-only mode.
- **`.env` excluded from Git** — secrets never reach the repository.
- **Private ECR repositories** — images not publicly accessible.

---

## 🧠 Key Technical Decisions

| Decision | Rationale |
|---|---|
| Streamlit over React + FastAPI | AI logic lives in Python; Streamlit eliminates the frontend/backend split, cutting development time in half |
| GPT-4o-mini over Gemini Flash | Superior instruction-following for structured outputs (SQL, JSON classifications); consistent behavior across prompts |
| Intent classifier before SQL | Prevents SQL generation failures on medical/conversational questions; routes to the correct handler without user friction |
| PostgreSQL in Docker (not RDS) | Cost — RDS adds ~$15/month for a demo project; Docker container on EC2 gives full control at zero extra cost |
| pg_trgm for fuzzy search | Handles cross-language product lookups (ibuprofen/ibuprofeno) natively in PostgreSQL without external search engines |
| ReportLab for PDF | Pure Python, no external services, full control over invoice layout and multilingual rendering |
| IAM Role over Access Keys | Industry best practice; credentials rotate automatically; eliminates credential leakage risk on the server |

---

## 💬 Example Queries

The assistant understands natural language in any language:

```
"Show me the top 10 products by price"
"¿Cuántas unidades de ibuprofeno tenemos en inventario?"
"What medications are good for back pain?"
"Quiero hacer un pedido de 2 cajas de amoxicilina"
"Show all pending orders this month"
"Je voudrais commander de la vitamine C"
"Which supplier provides the most products?"
```

---

## 👤 Author

<p align="center">
  Built with ❤️ by <a href="https://www.linkedin.com/in/david-pedroza-sanchez-9525b0346">David Pedroza Sánchez</a>
</p>
