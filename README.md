# NCAI-MAF

Stock-screener workflows built with FastAPI around AWS Bedrock Claude.

---

## 🧑‍💻 Local Development

### 1 Clone & install
```bash
git clone git@github.com:<org>/NCAI-MAF.git
cd NCAI-MAF
uv pip install -e .[dev]  # Install with dev dependencies
```

### 2 Environment variables  
Create **.env** in the project root (pull values from **Secrets Manager → `ncai/barrons-ticker/staging`**):
```dotenv
# Required environment variables for local development
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1
AWS_DEFAULT_REGION=us-east-1
is_staging=True        # crucial for local runs
ENVIRONMENT=staging
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=...
OPENAI_API_KEY=...     # For OpenAI model fallbacks
```
These are injected at runtime via  
`infrastructure/aws/secrets_manager.py` and `business/barrons/config/config.py`.

---

### 3 Chat endpoint (streamable)
```bash
uv run chat  # uvicorn api.enhanced_main:main
```
**Test**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
        "prompt": "I'm looking for stocks with strong growth potential. Show me companies with high revenue and earnings growth.", 
        "parameters": {
            "session_id": "ui-managed-session-id-13", "user_id": "logged-in-user-email-id-13"
            }, 
        "stream": true
        }'
```

---

### 4 Query endpoint
```bash
uv run start  # uvicorn api.main:main
```
**Test**
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
        "prompt":"Show me good growth stocks with PE ratio lower than 15."
      }'
```
A successful call returns **HTTP 200** with the standard API schema (`response`, `details`, …).

---

### 5 Docker development

The project can be run in Docker for consistency across environments.

#### Building the Docker image

If accessing private repositories (like agent-workflow):
```bash
# Build with GitHub token for private repo access
sudo docker build -t ncai-maf:local --build-arg GITHUB_TOKEN=your_github_token .
```

If all dependencies are public:
```bash
# Build without token
sudo docker build -t ncai-maf:local .
```

#### Running the Docker container
```bash
# Run with environment variables from .env file
sudo docker run -p 8000:8000 --env-file .env ncai-maf:local
```

#### Required .env variables for Docker
At minimum, the following variables should be in your .env file:
```dotenv
# AWS Configuration
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=us-east-1
AWS_DEFAULT_REGION=us-east-1

# Environment Settings
is_staging=True
ENVIRONMENT=staging

# Langfuse Observability
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_HOST=...

# Optional but recommended
OPENAI_API_KEY=...
MYSQL_DB_HOST=...
MYSQL_DB_NAME=...
MYSQL_DB_USER=...
MYSQL_DB_PASS=...
```

#### Testing the Docker container
```bash
# Test the API
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
        "prompt": "Show me tech stocks with high growth potential", 
        "parameters": {
            "session_id": "docker-test", 
            "user_id": "docker-user"
        }
      }'
```

---

## 🌐 Deployed URLs

| Environment | Base URL                                                         | Docs  |
|-------------|------------------------------------------------------------------|-------|
| **Staging** | <https://barrons-api-stg.ncgt.mpp-kwatee.com>                    | /docs |
| **Production** | *TBD*                                                         | /docs |

---

## 📑 MAF API Reference

### 1 `/feedback`

| Method | Path       | Purpose                         |
|--------|------------|---------------------------------|
| POST   | `/feedback` | Capture or update user feedback |

<details>
<summary>Request</summary>

```jsonc
{
  "prompt": "",
  "parameters": {
    "message_id": "55fded65-48a7-44da-aee6-1c25e6084f0a",
    "user_email": "logged-in-user-email-id-1",
    "session_id": "ui-managed-session-id-1",
    "preset_options": [],
    "feedback_comments": "",
    "feedback_type": false,
    "feedback_id": 3
  }
}
```
</details>

<details>
<summary>Response</summary>

```jsonc
{
  "response": {
    "error_message": "",
    "rds_data": [],
    "rds_columns": [],
    "feedback_id": 3,
    "message_id": "55fded65-48a7-44da-aee6-1c25e6084f0a",
    "user_email": "logged-in-user-email-id-1",
    "session_id": "ui-managed-session-id-1",
    "preset_options": [],
    "feedback_comments": "",
    "feedback_type": false
  },
  "request_id": "5b1f263d-0b19-43b1-aa2e-f4ed16da3e89",
  "conversation_id": "56158a1e-becb-4de2-abe6-93f2c93e7204",
  "workflow": "barrons_user_feedback",
  "status": null,
  "error": null,
  "data": null
}
```
</details>

---

### 2 `/chat`

| Method | Path   | Purpose                                   |
|--------|--------|-------------------------------------------|
| POST   | `/chat` | Conversational endpoint (optional stream) |

<details>
<summary>Request</summary>

```jsonc
{
  "prompt": "I'm looking for stocks with strong growth potential…",
  "parameters": {
    "session_id": "ui-managed-session-id-1",
    "user_id": "logged-in-user-email-id-1"
  },
  "stream": false,
  "conversation_id": "optional"
}
```
</details>

<details>
<summary>Response (truncated)</summary>

```jsonc
{
  "response": {
    "stock_data": { "...": "tabular results" },
    "stock_data_explanation": { "...": "LLM narrative" },
    "news_data_analysis": { "...": "LLM insights" },
    "follow_up_questions": { "...": "prompt suggestions" }
  },
  "request_id": "0679286c-e23c-4b1e-8350-46fc5fb57b22",
  "conversation_id": "auto-generated-id",
  "workflow": "master_chat_query",
  "status": null,
  "error": null,
  "data": null
}
```
</details>

---

### 3 `/query`

| Method | Path    | Purpose                         |
|--------|---------|---------------------------------|
| POST   | `/query` | One‑shot data query (no memory) |

Payload mirrors `/chat` minus `stream` and `conversation_id`.

---

### 4 Conversation management

| Method | Path                                  | Description              |
|--------|---------------------------------------|--------------------------|
| GET    | `/conversations/{conversation_id}`    | Retrieve full history    |
| DELETE | `/conversations/{conversation_id}`    | Delete conversation      |

---

### 5 Utility endpoints

| Path                     | Method | Response                    |
|--------------------------|--------|-----------------------------|
| `/health`                | GET    | `{"status":"healthy"}`       |
| `/status/{request_id}`   | GET    | Async processing status      |

---

## 🗃️ Envelope Schema

Every endpoint returns:

```jsonc
{
  "response": "<object|string>",
  "request_id": "<uuid>",
  "conversation_id": "<uuid|null>",
  "workflow": "<string>",
  "status": "<completed|processing|failed|null>",
  "error": "<string|null>",
  "data": "<object|null>"
}
```

---

## 🤝 Contributing

TO-DO

---

## 📄 License
