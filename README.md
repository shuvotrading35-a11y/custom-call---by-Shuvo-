# 🇧🇩 Bangladesh Custom Call Bot

Production-grade Telegram bot for automated voice call delivery across all Bangladesh mobile operators.  
Single HTTP GET API integration — no VoIP SDK, no complex telephony setup.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📞 TTS Call | Text-to-Speech via Call API (male/female, বাংলা/English) |
| 🎤 Voice Call | Upload audio → call API delivers it |
| 📂 Bulk Campaign | CSV/Excel/TXT upload, concurrent calls, live dashboard |
| 💳 Payments | bKash, Nagad, Rocket (manual + auto verification) |
| 🎁 Redeem Codes | Gift, Coupon, Promo, Referral |
| 👥 Referral System | Unique links, 24h hold, fraud prevention |
| ☎️ Support Tickets | Category-based, screenshot upload, admin reply |
| 👑 Admin Panel | Full user/payment/campaign/analytics management |

---

## 🛠 Tech Stack

- **Python 3.12+** · `python-telegram-bot v21+` · `FastAPI` · `SQLAlchemy 2.x async`
- **PostgreSQL 16** · **Redis 7** · **Celery 5** · **Docker Compose**

---

## 🚀 Quick Start

### 1. Clone & Configure

```bash
git clone <repo-url>
cd bangladesh-call-bot
cp .env.example .env
nano .env   # Fill in all required values
```

### 2. Required `.env` Values

```env
BOT_TOKEN=          # From @BotFather
WEBHOOK_URL=        # https://yourdomain.com
WEBHOOK_SECRET=     # Random secret string (generate with: openssl rand -hex 32)
ADMIN_IDS=          # Your Telegram ID (comma-separated for multiple)
CALL_API_URL=       # Your call API endpoint
CALL_API_KEY=       # Your call API key
DB_PASSWORD=        # Strong PostgreSQL password
```

### 3. Deploy with Docker

```bash
# Production
docker compose up -d

# View logs
docker compose logs -f bot
docker compose logs -f worker
```

### 4. SSL Setup (Let's Encrypt)

```bash
certbot certonly --standalone -d yourdomain.com
```

---

## 📁 Project Structure

```
bangladesh-call-bot/
├── bot/
│   ├── config/          # Settings, constants, logging
│   ├── database/        # SQLAlchemy models, migrations
│   ├── handlers/
│   │   ├── user/        # start, tts_call, profile, credits, redeem, referral, support
│   │   ├── admin/       # users, payments, analytics, api_config
│   │   └── bulk_calls/  # campaign_manager
│   ├── services/        # call_service, credit_service, number_validator
│   ├── tasks/           # Celery: bulk_tasks, call_tasks, payment_tasks, cleanup
│   ├── middlewares/     # auth, rate_limiter
│   ├── utils/           # keyboards, formatters, validators, file_parser
│   └── main.py          # Entry point
├── webhook/             # FastAPI webhook receiver
├── docker/              # Dockerfile, Dockerfile.worker, nginx.conf
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 📞 Call API Integration

The entire voice call system runs on **one HTTP GET request**:

```
GET {CALL_API_URL}?api_key=KEY&number=01XXXXXXXXX&message=TEXT&voice=female
```

**Response (success):**
```json
{"status": "success", "call_id": "abc123", "message": "Call initiated"}
```

**Response (error):**
```json
{"status": "error", "message": "Invalid number"}
```

Configure in Admin Panel → ⚙️ Settings → 🔑 API Configuration.  
All API calls are logged in the `api_logs` table.

---

## 🗄️ Database

Run migrations after first deploy:

```bash
docker compose exec bot alembic upgrade head
```

Or use `init_db()` for development (auto-creates all tables).

---

## 🇧🇩 Supported Operators

| Operator | Prefixes |
|---|---|
| Grameenphone | 017X, 013X |
| Robi | 018X |
| Airtel | 016X |
| Banglalink | 019X, 014X |
| Teletalk | 015X |

Numbers are automatically normalized to E.164 format: `+8801XXXXXXXXX`

---

## 👑 Admin Commands

| Command/Button | Action |
|---|---|
| `/admin` | Open admin panel |
| 👥 Users | Search, ban/unban, add credits |
| 💰 Payments | Approve/reject pending payments |
| 📊 Analytics | System stats dashboard |
| ⚙️ Settings | API URL/Key configuration + test |
| 📢 Broadcast | Send message to all users |

---

## 🔐 Security

- API key stored only in `.env`, never hardcoded
- API key masked in admin panel display  
- Every API call logged in `api_logs` table
- Every admin action logged in `audit_logs` table
- Per-user flood protection via Redis
- Blacklist system for numbers and users
- Rate limiting via Nginx

---

## 🐳 Docker Services

| Service | Description |
|---|---|
| `postgres` | PostgreSQL 16 database |
| `redis` | Redis 7 (cache + Celery broker) |
| `bot` | PTB application (webhook mode) |
| `worker` | Celery worker (bulk calls, async tasks) |
| `beat` | Celery beat (scheduled tasks) |
| `nginx` | Reverse proxy with SSL |

---

## 📊 Bulk Campaign Flow

1. Upload recipients (CSV/Excel/TXT or manual entry)
2. Auto-validate all BD numbers + blacklist check
3. Set message type (TTS text or voice upload)
4. Configure voice type, language, schedule
5. Credits deducted → campaign created
6. Celery worker dispatches calls concurrently
7. Live dashboard shows real-time progress
8. Download report on completion

---

## 🆘 Troubleshooting

**Bot not responding:**
```bash
docker compose logs bot --tail=50
```

**Celery tasks not running:**
```bash
docker compose logs worker --tail=50
docker compose exec redis redis-cli ping
```

**Database connection error:**
```bash
docker compose logs postgres
docker compose exec postgres psql -U callbot -c "\l"
```

---

## 📄 License

MIT License — Built by Shuvo MK
