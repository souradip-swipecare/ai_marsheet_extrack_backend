# Souradip Marksheet Extraction API

> A simple API that extracts data from marksheets using OCR and AI. Just upload image/pdf and get structured JSON!
try it ## https://aiintern.souradipproject.cloud/demo

Made by: **Souradip Biswas**
For better accuracy   we can use lamda function for concurrent response as it is very cpu heavy task
---
## Sample images
![Login Page](screenshots/loginpage1.png)   ![Login Page 2](screenshots/loginpage2.png)  
![Home Page](screenshots/home.png)        ![result Page](screenshots/result_1.png) ![result 2 Page](screenshots/result2.png)

![json copy Page](screenshots/json.png)
![Process Page](screenshots/processing.png)

---

## Architecture Overview

This API uses intelligent routing to extract structured data from marksheets with optimal speed and accuracy.

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT REQUEST                            │
│                   (Upload Image/PDF File)                        │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                ┌────────────▼────────────┐
                │     FastAPI Server      │
                │  - File validation      │
                │  - Rate limiting        │
                │  - JWT auth (optional)  │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │   File Processor        │
                │  - PDF type detection   │
                │  - Image preprocessing  │
                └────────────┬────────────┘
                             │
                ┌────────────▼────────────┐
                │  Quality Analyzer       │
                │  - Blur score (35%)     │
                │  - Contrast score (45%) │
                │  - Resolution (20%)     │
                └────────────┬────────────┘
                             │
                   Quality Score (0-100)
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
    Score >= 65                             Score < 65
         │                                       │
         ▼                                       ▼
┌────────────────┐                    ┌────────────────┐
│  OCR Service   │                    │  Skip OCR      │
│  - Multi-pass  │                    │  (poor quality)│
│  - Parallel    │                    └────────┬───────┘
│  - 5 techniques│                             │
└────────┬───────┘                             │
         │                                     │
    Confidence                                 │
         │                                     │
   ┌─────┴─────┐                              │
   │           │                              │
 >= 60%      < 60%                            │
   │           │                              │
   ▼           ▼                              ▼
┌──────┐  ┌────────────────────────────────────┐
│ Text │  │     Gemini Vision API              │
│  +   │  │  - Processes raw pixels            │
│ LLM  │  │  - Handles poor quality            │
└──┬───┘  │  - Best accuracy                   │
   │      └────────────────┬───────────────────┘
   │                       │
   └───────────┬───────────┘
               ▼
    ┌──────────────────┐
    │  Confidence      │
    │  Calculator      │
    │  - Field weights │
    │  - Weighted avg  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  JSON Response   │
    │  - Extracted data│
    │  - Confidences   │
    │  - Method used   │
    │  - Timing        │
    └──────────────────┘
```

### Processing Paths

| Path | Trigger | Speed | Accuracy | Cost |
|------|---------|-------|----------|------|
| **Text PDF** | Digital PDF with text | ⚡ 2-3s  | $ |
| **OCR → LLM** | Quality >= 65, OCR conf >= 60% | 🚀 7-8s  | $$ |
| **Vision Direct** | Quality < 65 | 🐌 16-26s  | $$$ |
| **Vision Fallback** | Quality >= 65, OCR conf < 60% | 🐌 20-31s  | $$$ |

### Technology Stack

- **Web Framework**: FastAPI (async, high-performance)
- **OCR Engine**: Tesseract 4.x (multi-pass with parallel processing)
- **LLM Provider**: Google Gemini 2.5 Flash (Vision + Text APIs)
- **Image Processing**: OpenCV, Pillow, PyMuPDF
- **Async Jobs**: Celery + Redis (optional, for background processing)
- **Database**: MongoDB (optional, for logging and analytics)
- **Deployment**: Docker + Gunicorn

---


## Folder Structure

```
ai_marsheet_extrack_backend/
│
├── app/                          # Main application code
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   │
│   ├── api/                      # API routes and security
│   │   ├── __init__.py
│   │   ├── routes.py             # Main router
│   │   ├── security.py           # API key authentication
│   │   └── v1/
│   │       └── routes.py         # v1 API endpoints (/extract, /batch, /health)
│   │
│   ├── core/                     # Configuration stuff
│   │   ├── __init__.py
│   │   ├── config.py             # Settings from .env file
│   │   └── logging.py            # Logger setup
│   │
│   ├── models/                   # Pydantic models
│   │   ├── __init__.py
│   │   └── schemas.py            # Request/Response schemas
│   │
│   ├── services/                 # Business logic
│   │   ├── __init__.py
│   │   ├── extraction.py         # LLM extraction (Gemini/OpenAI)
│   │   ├── ocr_service.py        # Tesseract OCR wrapper
│   │   └── prompts.py            # AI prompts for extraction
│   │
│   ├── static/
│   │   └── demo.html             # Frontend demo page
│   │
│   └── utils/                    # Helper functions
│       ├── __init__.py
│       ├── exceptions.py         # Custom exceptions
│       └── file_processor.py     # PDF/Image processing
│
├── extract/                      # Output folder (auto created)
│   ├── ocr_*.txt                 # Saved OCR text
│   └── output_*.json             # Saved extraction results
│
├── logs/                         # Log files
│   └── app.log
│
├── testdata/                     # Sample marksheets for testing
│   ├── marks_sheet_1.webp
│   ├── marks_sheet_2.webp
│   ├── shashank.jpg
│   └── ... more test files
│
├── tests/                        # Unit tests
│   └── test_api.py
│
├── .env                          # Environment variables (API keys etc)
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker config
├── docker-compose.yml            # Docker compose
└── README.md                     # This file!
```

---

## How It Works (Workflow)

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER UPLOADS FILE                        │
│                    (image: jpg/png/webp or PDF)                  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FILE VALIDATION                             │
│  • Check file size (max 10MB)                                    │
│  • Check file type (jpg/png/webp/pdf)                            │
│  • Reject if invalid                                             │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PDF TYPE DETECTION                            │
│  • Count characters per page                                     │
│  • If avg >= 80 chars/page → text-based PDF                      │
│  • If avg < 80 chars/page → scanned/image PDF                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                TEXT PDF                  IMAGE PDF / IMAGE
                    │                         │
                    ▼                         ▼
        ┌─────────────────────┐   ┌─────────────────────┐
        │  DIRECT TEXT EXTRACT│   │  IMAGE QUALITY CHECK │
        │  • PyMuPDF text     │   │  • Blur score        │
        │  • No OCR needed    │   │  • Contrast score    │
        │  • Fastest path     │   │  • Resolution score  │
        └─────────────────────┘   │  • Overall: 0-100    │
                    │             └─────────────────────┘
                    │                         │
                    │             ┌───────────┴───────────┐
                    │             │                       │
                    │       Quality >= 65           Quality < 65
                    │             │                       │
                    │             ▼                       ▼
                    │   ┌──────────────────┐   ┌──────────────────┐
                    │   │  MULTI-PASS OCR  │   │  SKIP OCR        │
                    │   │  • 5 preprocessing│   │  • Low quality   │
                    │   │  • Parallel runs  │   │  • Use vision    │
                    │   │  • Pick best      │   │    directly      │
                    │   └──────────────────┘   └──────────────────┘
                    │             │                       │
                    │             ▼                       │
                    │   ┌──────────────────┐             │
                    │   │  OCR CONFIDENCE  │             │
                    │   │  • Weighted avg  │             │
                    │   │  >= 60% threshold│             │
                    │   └──────────────────┘             │
                    │             │                       │
                    │   ┌─────────┴────────┐             │
                    │   │                  │             │
                    │  OCR OK          OCR Poor          │
                    │   │                  │             │
                    ▼   ▼                  ▼             ▼
        ┌────────────────────────┐   ┌────────────────────────┐
        │   TEXT → GEMINI        │   │   IMAGE → GEMINI VISION│
        │   • Fast extraction    │   │   • Highest accuracy   │
        │   • Text-only prompt   │   │   • Handles poor scans │
        │   • Lower cost         │   │   • Slower processing  │
        └────────────────────────┘   └────────────────────────┘
                    │                           │
                    └──────────┬────────────────┘
                               ▼
                ┌──────────────────────────────┐
                │   CONFIDENCE CALCULATION     │
                │   • Field-level scores       │
                │   • Weighted by importance   │
                │   • Critical fields: 2.0x    │
                │   • Important fields: 1.5x   │
                │   • Other fields: 1.0x       │
                └──────────────────────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │   STRUCTURED JSON RESPONSE   │
                │   • Extracted data           │
                │   • Confidence scores        │
                │   • Processing method        │
                │   • Timing information       │
                └──────────────────────────────┘
```

---
## PDF Processing Logic

When you upload a PDF:

- **If the PDF contains selectable text** (digital PDF), we extract the text directly for faster and more accurate results.
- **If the PDF is image-based** (scanned or photographed), we convert each page to an image and run OCR (Optical Character Recognition) to extract the text.

This ensures the best possible extraction quality and speed for both digital and scanned PDFs.

---

## Async Job Processing Architecture

The API supports background job processing using **Celery** with **Redis** as the message broker and result backend. This allows handling long-running extraction tasks without blocking the API.

### Job Flow

```
Client Request → API Endpoint → Celery Task Queue → Worker Pool → Result Storage
                      ↓                                   ↓              ↓
                Job ID returned                    Progress updates    Result retrieval
```

### How Jobs Work

1. **Job Submission**: Client uploads file, receives `job_id` immediately
2. **Task Queuing**: Celery queues the task in Redis with status `PENDING`
3. **Worker Processing**: Worker picks up task, updates status to `PROCESSING`
4. **Progress Tracking**: Task updates progress (0-100%) throughout execution
5. **Completion**: Final status becomes `SUCCESS` or `FAILURE`
6. **Result Storage**: Results cached in Redis for 1 hour

### Job States

| State | Description | Progress |
|-------|-------------|----------|
| `PENDING` | Task queued, waiting for worker | 0% |
| `PROCESSING` | Worker actively processing | 10-90% |
| `SUCCESS` | Extraction completed | 100% |
| `FAILURE` | Task failed with error | - |

### Progress Breakdown

| Progress | Activity |
|----------|----------|
| 10% | Task started, initializing |
| 20% | File validation and type detection |
| 40% | PDF/image processing complete |
| 45% | Quality assessment done |
| 50% | OCR started (if needed) |
| 60-70% | OCR complete or Vision API called |
| 90% | Extraction complete, finalizing |
| 100% | Response ready |

### Worker Configuration

- **Task Timeout**: 5 minutes hard limit (4 minutes soft limit)
- **Prefetch**: 1 task at a time (fair distribution across workers)
- **Max Tasks Per Child**: 50 (prevents memory leaks)
- **Result Expiry**: 1 hour
- **Acknowledgement**: Late (after task completion for reliability)

---

## Image Quality Assessment

Before running OCR or sending to Vision API, we assess image quality to determine the optimal processing path. This saves time and API costs.

### Quality Metrics

The quality analyzer evaluates three dimensions:

#### 1. Blur Detection (35% weight)
- **Method**: Laplacian variance
- **Threshold**: 100.0 variance units
- **Score**: 
  - >= 200 variance → 100 points
  - >= 100 variance → 50-100 points (linear)
  - < 100 variance → 0-50 points (linear)

#### 2. Contrast Detection (45% weight)
- **Method**: Standard deviation of grayscale
- **Threshold**: 35 std dev
- **Score**:
  - >= 70 std dev → 100 points
  - < 70 std dev → 0-100 points (linear)

#### 3. Resolution Check (20% weight)
- **Method**: Minimum dimension (width or height)
- **Threshold**: 800 pixels
- **Score**:
  - >= 1600 pixels → 100 points
  - >= 800 pixels → 50-100 points (linear)
  - < 800 pixels → 0-50 points (linear)

### Quality Score Calculation

```
quality_score = (blur_score × 0.35) + (contrast_score × 0.45) + (resolution_score × 0.20)
```

### Routing Decision

| Quality Score | Recommended Path | Reason |
|--------------|------------------|--------|
| >= 65 | OCR → LLM | High quality, OCR will work well |
| < 65 | Direct Vision API | Poor quality, skip OCR overhead |

**Benefits**:
- Saves 5-10 seconds on low-quality images (skips OCR)
- Better accuracy on poor scans (Vision API handles them better)
- Cost optimization (OCR + LLM cheaper than Vision API when quality is good)

---

## Multi-Pass OCR (How It Works)

We run Tesseract OCR **5 times in PARALLEL** with different image preprocessing techniques and pick the best result. This handles various image qualities, lighting, and backgrounds.

### Parallel Processing (8 Workers)

All 5 OCR passes run **simultaneously** using Python's `ThreadPoolExecutor` with 4 workers:

```
BEFORE (Sequential):
Pass 1 → Pass 2 → Pass 3 → ... → Pass 5
[============= 15 seconds =============]

AFTER (Parallel with 8 workers):
Pass 1  ──┐
Pass 2  ──┤
Pass 3  ──┤
Pass 4  ──┼──→ All run at the same time!
...       │
Pass 5 ──┘
[=== 4-5 seconds ===]
```

**Result: ~3-4x faster OCR processing!**

**Note:** If your system doesn't support `ThreadPoolExecutor` (some embedded systems or restricted environments), the service will automatically fall back to sequential processing. You can also manually disable parallel processing by setting `OCR_USE_PARALLEL=false` in your `.env` file.

### Preprocessing Passes new 
passes through only 5vlayer

        return [
            (gray, "--oem 3 --psm 3"),
            (enhanced, "--oem 3 --psm 6"),
            (otsu, "--oem 3 --psm 6"),
            (adaptive, "--oem 3 --psm 6"),
            (sharpened, "--oem 3 --psm 3"),
        ]

### Preprocessing Passes Old 

| Pass | Technique | Purpose |
|------|-----------|---------|
| 1-2 | Grayscale + CLAHE + Denoise | Basic enhancement |
| 3-4 | Scaled image (2x or 1.5x) | For small/low-res images |
| 5 | Bilateral filter | Edge-preserving smoothing |
| 6 | Otsu's binarization | Automatic threshold |
| 7-9 | Adaptive threshold (blocks: 11, 15, 21) | Handle uneven lighting |
| 10-11 | Morphological close + open | Clean up text edges |
| 12 | Sharpened (unsharp masking) | Improve text clarity |
| 13-16 | Different PSM modes (4, 6, 11, 12) | Different text layouts |
| 17 | Inverted image | For dark backgrounds |

### PSM Modes Explained

| Mode | Name | When Used |
|------|------|-----------|
| PSM 3 | Auto page segmentation | Default, works for most |
| PSM 4 | Single column | Vertical text layouts |
| PSM 6 | Uniform block | Tables, structured text |
| PSM 11 | Sparse text | Find scattered text |
| PSM 12 | Sparse text + OSD | With orientation detection |

### Best Result Selection

After all passes, we score each result:

```
Score = (alpha_count * 0.4) + (confidence * 100 * 0.4) + (word_count * 0.2)
```

| Factor | Weight | Why |
|--------|--------|-----|
| Alpha count | 40% | More real characters = less garbage |
| Confidence | 40% | Higher confidence = better quality |
| Word count | 20% | More words = more complete extraction |

---

## Quick Start

### 1. Clone and setup

```bash
git clone https://github.com/souradip-swipecare/ai_marsheet_extrack_backend.git
cd ai_marsheet_extrack_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install loguru
```

### 2. Install Tesseract OCR

**Mac:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki


### 3. Setup environment variables

Create `.env` file:
```env
# App Settings
APP_NAME="Souradip Marksheet Extraction API"
DEBUG=false

# Gemini API Key (get from https://aistudio.google.com/apikey)
GOOGLE_API_KEY=your_gemini_api_key_here

# Model settings
DEFAULT_LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash

# OCR settings
OCR_CONFIDENCE_THRESHOLD=0.60
SAVE_OCR_TEXT=true
OCR_USE_PARALLEL=true  # Set to false if ThreadPoolExecutor not supported


```


### 4. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
celery run
celery -A app.core.celery_config worker --loglevel=info --concurrency=1
```

### 5. Open in browser locally

- **Demo Page:** http://localhost:8000/
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

---

## API Endpoints

### Async Job Endpoints

When Celery is enabled, you can submit jobs asynchronously and check their status.

#### Submit Async Job

```
POST /api/v1/jobs/submit
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | Marksheet image or PDF |
| apikey | string | No | Your Gemini API key (optional) |

**Response:**
```json
{
  "success": true,
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Job submitted successfully"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/submit" \
  -F "file=@marksheet.jpg"
```

---

#### Check Job Status

```
GET /api/v1/jobs/{job_id}/status
```

**Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "progress": 65,
  "message": "OCR complete, running LLM extraction"
}
```

**Status Values:**
- `queued` (0%): Job waiting in queue
- `processing` (10-90%): Job actively running
- `completed` (100%): Job finished successfully
- `failed`: Job encountered an error

---

#### Get Job Result

```
GET /api/v1/jobs/{job_id}/result
```

**Response (if completed):**
```json
{
  "success": true,
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "data": {
    "candidate": { ... },
    "subjects": [ ... ],
    "result": { ... },
    "extraction_confidence": 0.89
  },
  "extraction_method": "ocr_text_llm",
  "processing_time_ms": 7234.56
}
```

**Response (if still processing):**
```json
{
  "success": false,
  "error": "Job still processing",
  "status": "processing",
  "progress": 45
}
```

---

#### Batch Job Submission

```
POST /api/v1/jobs/batch
```

Upload multiple files and get individual job IDs for tracking.

**Response:**
```json
{
  "success": true,
  "batch_id": "batch_20260605_123456",
  "total_jobs": 5,
  "job_ids": [
    "job-1-uuid",
    "job-2-uuid",
    "job-3-uuid",
    "job-4-uuid",
    "job-5-uuid"
  ]
}
```

---

#### Batch Status Check

```
GET /api/v1/jobs/batch/{batch_id}/status
```

**Response:**
```json
{
  "batch_id": "batch_20260605_123456",
  "total": 5,
  "completed": 3,
  "processing": 1,
  "failed": 0,
  "queued": 1,
  "progress": 60,
  "jobs": [
    {"job_id": "job-1-uuid", "status": "completed"},
    {"job_id": "job-2-uuid", "status": "completed"},
    {"job_id": "job-3-uuid", "status": "completed"},
    {"job_id": "job-4-uuid", "status": "processing"},
    {"job_id": "job-5-uuid", "status": "queued"}
  ]
}
```

---

### Health Check

```
GET /api/v1/health
```

---

## Authentication (JWT)

The API supports JWT (JSON Web Token) based authentication for secure access control. When MongoDB is enabled, all extraction endpoints require authentication.

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. User Registration/Login                                      │
│     POST /api/v1/auth/login                                      │
│     Body: { "email": "user@example.com", "password": "pass123" } │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Receive JWT Token                                            │
│     Response: { "access_token": "eyJhbGci...", "token_type": ... }│
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Use Token in API Requests                                    │
│     Authorization: Bearer eyJhbGci...                            │
│     (Include in header of every request)                         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Token Validation                                             │
│     • Server validates signature                                 │
│     • Checks expiration (default: 30 minutes)                    │
│     • Extracts user_id from token                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. Process Request                                              │
│     • Log activity with user_id                                  │
│     • Execute extraction                                         │
│     • Return results                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

### 1. User Registration

```
POST /api/v1/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "your_secure_password",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "user_id": "usr_1234567890abcdef",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

---

### 2. User Login (Get JWT Token)

```
POST /api/v1/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "your_secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidXNyXzEyMzQ1Njc4OTBhYmNkZWYiLCJleHAiOjE3MTc2MDAwMDB9.signature",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

**Save the token:**
```bash
# Store token in variable for reuse
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}' \
  | jq -r '.access_token')

echo $TOKEN
```

---

### 3. Using JWT Token in API Requests

**IMPORTANT:** JWT tokens are passed in the `Authorization` header, **NOT** in request body or query parameters.

#### Format:
```
Authorization: Bearer <your_jwt_token>
```

#### Submit Job with JWT Authentication

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/submit" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -F "file=@marksheet.jpg"
```

#### Check Job Status with JWT

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/status" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### Get Job Result with JWT

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/{job_id}/result" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---


## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_api.py::TestMarksheetExtraction -v

# Run with output
pytest tests/ -v -s
```

---

## Docker

```bash
# Build and run
docker-compose up --build

# Or just build
docker build -t marksheet-api .
docker run -p 8000:8000 --env-file .env marksheet-api
```

---

## Extraction Methods

The API automatically selects the optimal extraction method based on file type, quality assessment, and OCR confidence. Each method is optimized for specific scenarios.

### Method Selection Flow

```
PDF with text (>80 chars/page) → text_pdf_direct
    ↓
Image/Scanned PDF
    ↓
Quality Assessment
    ↓
├─ Quality >= 65 → Run OCR
│   ├─ OCR confidence >= 60% → ocr_text_llm
│   └─ OCR confidence < 60% → vision_ocr_fallback
│
└─ Quality < 65 → vision_direct (skip OCR)
```

### Available Methods

| Method | Trigger Conditions | Processing Steps | Speed | Accuracy | Cost |
|--------|-------------------|------------------|-------|----------|------|
| `text_pdf_direct` | PDF with selectable text (avg >= 80 chars/page) | PyMuPDF text extraction → LLM parsing | ⚡ Fastest (2-3s) | ⭐⭐⭐⭐⭐ | $ Lowest |
| `ocr_text_llm` | Quality >= 65 AND OCR confidence >= 60% | Multi-pass OCR → Pick best → LLM parsing | 🚀 Fast (5-8s) | ⭐⭐⭐⭐ | $$ Low |
| `vision_direct` | Quality < 65 (poor image) | Raw image → Vision API directly | 🐌 Slow (15-25s) | ⭐⭐⭐⭐⭐ | $$$ High |
| `vision_ocr_fallback` | Quality >= 65 BUT OCR confidence < 60% | OCR attempted but failed → Vision API | 🐌 Slow (18-30s) | ⭐⭐⭐⭐ | $$$ High |

### Method Details

#### 1. text_pdf_direct
**Best for:** Digital PDFs, typed documents, modern marksheets

**How it works:**
1. PyMuPDF extracts native text from PDF
2. Text sent to LLM for structured parsing
3. No OCR needed (text already available)

**Advantages:**
- Fastest processing time
- Highest accuracy (no OCR errors)
- Lowest API cost (text-only LLM call)

**Example use case:** Modern university marksheets in PDF format

---

#### 2. ocr_text_llm
**Best for:** High-quality scans, clear images, good lighting

**How it works:**
1. Image quality assessed (blur, contrast, resolution)
2. Multi-pass OCR with 5 preprocessing techniques
3. Best OCR result selected based on scoring
4. OCR text sent to LLM for parsing

**Advantages:**
- Good balance of speed and accuracy
- Lower cost than Vision API
- Reliable for quality images

**Example use case:** Mobile phone photos of marksheets in good lighting

---

#### 3. vision_direct
**Best for:** Poor quality images, bad lighting, damaged documents

**How it works:**
1. Quality assessment detects poor image (blur/contrast issues)
2. Skip OCR entirely (would produce garbage)
3. Raw image sent directly to Gemini Vision API
4. Vision model extracts data from pixels

**Advantages:**
- Best accuracy for poor quality sources
- Handles damaged/faded documents
- No OCR preprocessing overhead

**Disadvantages:**
- Slower processing (Vision API is compute-intensive)
- Higher API costs

**Example use case:** Old photocopied marksheets, water-damaged documents

---

#### 4. vision_ocr_fallback
**Best for:** Images that look clear but have OCR-resistant issues

**How it works:**
1. Quality assessment passes (image looks OK)
2. OCR runs but produces low confidence (<60%)
3. System falls back to Vision API
4. Both OCR attempt time and Vision time add up

**Why this happens:**
- Unusual fonts or handwriting
- Text on complex backgrounds
- Watermarks interfering with OCR
- Non-standard layouts

**Example use case:** Artistic/designed marksheets with decorative fonts

---

### Performance Comparison

**Processing Time Breakdown:**

| Method | Quality Check | OCR | LLM/Vision | Total |
|--------|--------------|-----|------------|-------|
| `text_pdf_direct` | 100ms | 0s | 2-3s | **2-3s** |
| `ocr_text_llm` | 500ms | 4-5s | 2-3s | **7-8s** |
| `vision_direct` | 500ms | 0s | 15-25s | **16-26s** |
| `vision_ocr_fallback` | 500ms | 4-5s | 15-25s | **20-31s** |

**Cost Estimate (per extraction):**

| Method | API Calls | Estimated Cost |
|--------|-----------|----------------|
| `text_pdf_direct` | 1 text-only LLM | ~$0.00005 |
| `ocr_text_llm` | 1 text-only LLM | ~$0.00006 |
| `vision_direct` | 1 Vision API | ~$0.0003 |
| `vision_ocr_fallback` | 1 Vision API | ~$0.0003 |

---

## Processing Pipeline Details

Here's a detailed breakdown of what happens during extraction, with actual timing data for each method.

### Pipeline Stages

#### Stage 1: File Reception & Validation (100-200ms)

```
┌─────────────────────────────┐
│  1. Read file from upload   │ → 50ms
│  2. Check file size         │ → 10ms
│  3. Validate file type      │ → 10ms
│  4. Load into memory        │ → 30-100ms
└─────────────────────────────┘
```

**Potential Issues:**
- File size > 10MB → rejected
- Invalid file type → rejected
- Corrupted file → rejected

---

#### Stage 2: PDF Type Detection (100-500ms)

**For PDF files only:**

```
┌─────────────────────────────┐
│  1. Open PDF with PyMuPDF   │ → 50ms
│  2. Extract text per page   │ → 20-200ms per page
│  3. Count characters        │ → 10ms
│  4. Classify PDF type       │ → 10ms
└─────────────────────────────┘
```

**Decision Logic:**
- Avg chars/page >= 80 → Text-based PDF (proceed to text extraction)
- Avg chars/page < 80 → Image-based PDF (convert to images)

---

#### Stage 3: Image Processing (200-800ms)

**For image files or image-based PDFs:**

```
┌─────────────────────────────┐
│  1. Decode image bytes      │ → 50-200ms
│  2. Convert color mode      │ → 50-100ms
│  3. Resize if needed        │ → 100-300ms (if >4096px)
│  4. Optimize for API        │ → 50-200ms
└─────────────────────────────┘
```

**For multi-page PDFs:**
- Each page rendered at 300 DPI → 200-500ms per page
- Total: 200ms × pages

---

#### Stage 4: Quality Assessment (300-600ms)

```
┌─────────────────────────────┐
│  1. Convert to grayscale    │ → 50ms
│  2. Calculate blur score    │ → 100-200ms (Laplacian variance)
│  3. Calculate contrast      │ → 50-100ms (std deviation)
│  4. Measure resolution      │ → 10ms
│  5. Compute quality score   │ → 10ms
│  6. Decide routing          │ → 10ms
└─────────────────────────────┘
```

**Output:** Quality score (0-100) + routing decision (OCR vs Vision)

---

#### Stage 5A: Multi-Pass OCR (4-6 seconds)

**Only if quality >= 65:**

```
┌─────────────────────────────┐
│  Preprocessing Techniques:   │
│  1. Grayscale + enhance     │ ┐
│  2. CLAHE + denoise         │ │
│  3. Otsu threshold          │ ├─ All run in parallel
│  4. Adaptive threshold      │ │  (ThreadPoolExecutor)
│  5. Sharpen + enhance       │ ┘
│                             │ → 4-6 seconds total
│  6. Score all results       │ → 50ms
│  7. Pick best result        │ → 10ms
└─────────────────────────────┘
```

**Scoring Formula:**
```
score = (alphanumeric_count × 0.4) + 
        (confidence × 100 × 0.4) + 
        (word_count × 0.2)
```

**Output:** Best OCR text + confidence score

---

#### Stage 5B: OCR Confidence Check (50ms)

```
┌─────────────────────────────┐
│  1. Count words by conf     │ → 20ms
│  2. Calculate weighted avg  │ → 20ms
│  3. Apply bonus if good     │ → 10ms
└─────────────────────────────┘
```

**Decision:**
- OCR confidence >= 60% → Use OCR text path
- OCR confidence < 60% → Fallback to Vision API

---

#### Stage 6A: LLM Text Extraction (2-4 seconds)

**For text-based PDFs or good OCR:**

```
┌─────────────────────────────┐
│  1. Build text prompt       │ → 10ms
│  2. Call Gemini API         │ → 1500-3500ms
│  3. Parse JSON response     │ → 50-200ms
│  4. Calculate confidence    │ → 50ms
└─────────────────────────────┘
```

**API Call Details:**
- Model: gemini-2.5-flash
- Temperature: 0.1 (deterministic)
- Max tokens: 10,000
- Network latency: 200-500ms
- Processing time: 1-3 seconds

---

#### Stage 6B: Vision API Extraction (15-30 seconds)

**For poor quality or OCR fallback:**

```
┌─────────────────────────────┐
│  1. Encode images           │ → 100-300ms
│  2. Build vision prompt     │ → 10ms
│  3. Call Gemini Vision API  │ → 14000-28000ms ⚠️ SLOW
│  4. Parse JSON response     │ → 50-200ms
│  5. Calculate confidence    │ → 50ms
└─────────────────────────────┘
```

**Why Vision API is slow:**
- Processes every pixel in image
- Runs multiple vision models internally
- Handles OCR + understanding simultaneously
- Network transfer for image data

---

#### Stage 7: Confidence Calculation (50-100ms)

```
┌─────────────────────────────┐
│  1. Extract all field confs │ → 20ms
│  2. Apply field weights     │ → 20ms
│  3. Calculate weighted avg  │ → 30ms
│  4. Round to 3 decimals     │ → 10ms
│  5. Clamp to 0.0-1.0 range  │ → 10ms
└─────────────────────────────┘
```

**Field Weights Applied:**
- Critical fields (name, roll_number, result_status): 2.0x
- Important fields (marks, subject_name): 1.5x
- Other fields: 1.0x

---

#### Stage 8: Response Building (50-100ms)

```
┌─────────────────────────────┐
│  1. Serialize JSON          │ → 30-50ms
│  2. Add metadata            │ → 10ms
│  3. Calculate total time    │ → 10ms
│  4. Save to file (optional) │ → 20-50ms
└─────────────────────────────┘
```

---

### Total Time by Method

| Method | File Val | PDF/Image | Quality | OCR | LLM/Vision | Confidence | Response | **Total** |
|--------|---------|-----------|---------|-----|------------|------------|----------|-----------|
| `text_pdf_direct` | 150ms | 300ms | - | - | 2500ms | 70ms | 80ms | **~3.1s** |
| `ocr_text_llm` | 150ms | 500ms | 500ms | 5000ms | 2500ms | 70ms | 80ms | **~8.8s** |
| `vision_direct` | 150ms | 500ms | 500ms | - | 20000ms | 70ms | 80ms | **~21.3s** |
| `vision_ocr_fallback` | 150ms | 500ms | 500ms | 5000ms | 20000ms | 70ms | 80ms | **~26.3s** |

### Performance Optimization Tips

**To minimize processing time:**

1. **Upload text-based PDFs when possible** → 3x faster (text_pdf_direct)
2. **Ensure good lighting when photographing** → Better quality = OCR path
3. **Use higher resolution images** → Better quality scores
4. **Avoid shadows and glare** → Better contrast scores
5. **Keep documents flat** → Less blur
6. **Use async jobs for batch processing** → Process multiple files in parallel

**What NOT to do:**
- ❌ Upload low-res/blurry images (forces Vision API)
- ❌ Upload huge files >10MB (rejected)
- ❌ Upload photos with fingers/objects visible (confuses Vision)
- ❌ Upload rotated/sideways images (reduces OCR accuracy)

---

## Configuration Options

All settings in `.env` file:

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | "Souradip Marksheet Extraction API" | Application name |
| `APP_VERSION` | "1.0.0" | API version |
| `DEBUG` | false | Enable debug mode (verbose logging) |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | - | Your Gemini API key (required) |
| `GEMINI_MODEL` | gemini-2.5-flash | Gemini model to use |
| `DEFAULT_LLM_PROVIDER` | gemini | LLM provider (only "gemini" supported currently) |

### OCR Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_CONFIDENCE_THRESHOLD` | 0.60 | Min OCR confidence to use text path (0.0-1.0) |
| `OCR_USE_PARALLEL` | true | Enable parallel OCR processing |
| `SAVE_OCR_TEXT` | true | Save OCR output to extract/ folder |

### File Upload Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE_MB` | 10 | Max file upload size in MB |
| `ALLOWED_EXTENSIONS` | jpg,jpeg,png,webp,pdf | Allowed file extensions |

### Celery & Redis (Async Jobs)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_ENABLED` | false | Enable async job processing |
| `REDIS_HOST` | localhost | Redis server host |
| `REDIS_PORT` | 6379 | Redis server port |
| `REDIS_DB` | 0 | Redis database number |
| `REDIS_PASSWORD` | - | Redis password (optional) |

**To enable async jobs:**
```env
CELERY_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
```

Then start Celery worker:
```bash
celery -A app.core.celery_config worker --loglevel=info --concurrency=2
```

### MongoDB (User Tracking & Logging)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_ENABLED` | false | Enable MongoDB logging |
| `MONGODB_URL` | - | MongoDB connection string |
| `MONGODB_DB_NAME` | marksheet_extraction | Database name |

**To enable MongoDB:**
```env
MONGODB_ENABLED=true
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=marksheet_extraction
```

**What gets logged:**
- Extraction requests (user_id, filename, status)
- Processing times and methods used
- Success/failure rates
- API usage statistics
- Cost estimates per request

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | true | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | 100 | Max requests per minute per IP |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | - | JWT signing key (required if auth enabled) |
| `JWT_ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | JWT token expiry time |

---

---

## How Confidence Score is Calculated

The API calculates confidence at multiple stages to provide reliability indicators for extracted data. Each stage contributes to the final confidence assessment.

### 1. Image Quality Confidence

**Before processing**, we assess the raw image quality:

```
quality_score = (blur_score × 0.35) + (contrast_score × 0.45) + (resolution_score × 0.20)
```

**Components:**
- **Blur Score**: Laplacian variance method (threshold: 100.0)
- **Contrast Score**: Grayscale standard deviation (threshold: 35)
- **Resolution Score**: Minimum dimension check (threshold: 800px)

**Impact on Processing:**
- Score >= 65: Route to OCR path (faster, cheaper)
- Score < 65: Route directly to Vision API (better accuracy)

### 2. OCR Confidence (Tesseract)

**If OCR is used**, Tesseract provides word-level confidence scores (0-100). We calculate weighted average:

```
For each word:
  - High confidence word (>=70%): weight = 1.5
  - Low confidence word (<70%):  weight = 1.0

weighted_avg = sum(confidence × weight) / sum(weights)

Bonus: If >70% words are high confidence → +10% boost (capped at 1.0)
```

**Example Calculation:**
```
Words: ["RAHUL" (95%), "KUMAR" (88%), "x7z" (30%)]

Weighted calculation:
- RAHUL: 0.95 × 1.5 = 1.425
- KUMAR: 0.88 × 1.5 = 1.32
- x7z:   0.30 × 1.0 = 0.30

Average = (1.425 + 1.32 + 0.30) / (1.5 + 1.5 + 1.0) = 0.76 (76%)
```

**Routing Decision:**
- OCR confidence >= 60%: Send OCR text to LLM (fast path)
- OCR confidence < 60%: Fallback to Vision API (accuracy path)

### 3. Field-Level Confidence (LLM)

Gemini returns confidence for each extracted field based on:
- **Visual clarity**: How clearly the text is visible in the image/OCR
- **Pattern matching**: Does the value match expected format? (e.g., dates, numbers)
- **Contextual consistency**: Does it align with other fields?

| Confidence Range | Interpretation |
|-----------------|----------------|
| 0.9 - 1.0 | Excellent - Field perfectly clear and validated |
| 0.7 - 0.9 | Good - Field readable with high certainty |
| 0.5 - 0.7 | Fair - Field detected but some ambiguity |
| 0.3 - 0.5 | Poor - Field partially visible or uncertain |
| 0.0 - 0.3 | Very Low - Field barely visible or inferred |

### 4. Overall Extraction Confidence

The final `extraction_confidence` is a **weighted average** across all extracted fields, with critical fields getting higher weight:

```python
Field weights:
  Critical fields (2.0x):  name, roll_number, result_status
  Important fields (1.5x): obtained_marks, total_marks, subject_name
  Other fields (1.0x):     All remaining fields (board, grade, percentage, etc.)

overall_confidence = sum(field_confidence × weight) / sum(weights)
```

**Implementation Details:**
- The algorithm **recursively traverses** all extracted fields
- Each field with a `{"value": ..., "confidence": ...}` structure contributes to the score
- Weights are applied based on field importance for marksheet validation
- Final score is **rounded to 3 decimal places** and clamped between 0.0 - 1.0

**Example:**
```
Extracted fields:
- name: 0.95 (weight: 2.0) → 1.90
- roll_number: 0.92 (weight: 2.0) → 1.84
- result_status: 0.98 (weight: 2.0) → 1.96
- obtained_marks: 0.91 (weight: 1.5) → 1.365
- total_marks: 0.88 (weight: 1.5) → 1.32
- subject_name: 0.90 (weight: 1.5) → 1.35
- father_name: 0.85 (weight: 1.0) → 0.85

overall = (1.90 + 1.84 + 1.96 + 1.365 + 1.32 + 1.35 + 0.85) / (2.0 + 2.0 + 2.0 + 1.5 + 1.5 + 1.5 + 1.0)
overall = 10.585 / 11.5 = 0.920 (92%)
```

**Note:** This calculation is performed by the `GeminiExtractor._calculate_confidence()` method in `app/services/extraction.py` during async processing.

### Confidence vs Processing Method

| Extraction Method | Typical Confidence | Notes |
|------------------|-------------------|-------|
| `text_pdf_llm` | 0.85 - 0.95 | Highest (native text extraction) |
| `ocr_text_llm` | 0.75 - 0.90 | Good (quality OCR + LLM) |
| `vision_direct` | 0.70 - 0.90 | Variable (depends on image quality) |
| `vision_ocr_fallback` | 0.65 - 0.85 | Lower (poor quality source) |

### Using Confidence Scores

**Recommended thresholds for automation:**
- **>= 0.85**: Safe to auto-process without review
- **0.70 - 0.85**: Review recommended for critical operations
- **< 0.70**: Manual verification required

---

## Quick Reference Guide

### Common Scenarios

#### "My extraction is slow (>20 seconds)"

**Likely cause:** Vision API being used instead of OCR path

**Solutions:**
1. Check image quality - is it blurry or low-contrast?
2. Ensure good lighting when photographing
3. Upload higher resolution images (>800px minimum dimension)
4. If PDF, make sure it's text-based not scanned
5. Check logs to see which method was used (`extraction_method` in response)

---

#### "Confidence scores are low (<0.70)"

**Likely causes:**
- Poor image quality
- OCR failed to read text clearly
- Unusual fonts or handwriting
- Complex background or watermarks

**Solutions:**
1. Re-photograph with better lighting
2. Ensure document is flat (no wrinkles or curves)
3. Remove any obstructions (hands, shadows)
4. Try scanning instead of photographing
5. Clean the document before capturing

---

#### "Getting 'File too large' error"

**Cause:** File exceeds 10MB limit

**Solutions:**
1. Reduce image resolution (4096px max dimension is enough)
2. Compress PDF before uploading
3. Convert multi-page PDF to single page if possible
4. Use JPEG instead of PNG (smaller file size)

---

#### "Want faster processing for bulk files"

**Solutions:**
1. Enable Celery for async processing:
   ```bash
   # In .env
   CELERY_ENABLED=true
   REDIS_HOST=localhost
   
   # Start worker
   celery -A app.core.celery_config worker --concurrency=4
   ```
2. Use batch endpoints: `/api/v1/jobs/batch`
3. Process multiple workers in parallel
4. Submit jobs and poll for results

---

#### "How to reduce API costs?"

**Cost optimization tips:**
1. Upload text-based PDFs when possible (cheapest: ~$0.00005/request)
2. Ensure good image quality to trigger OCR path (cheap: ~$0.00006)
3. Avoid forcing Vision API for clear images
4. Batch process during off-peak hours
5. Cache results for repeated documents

**Cost breakdown:**
- Text PDF → LLM: ~$0.00005
- OCR → LLM: ~$0.00006
- Vision API: ~$0.0003 (5-6x more expensive)

---

#### "Need to track user activity and API usage"

**Solution:** Enable MongoDB logging

```env
# In .env
MONGODB_ENABLED=true
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=marksheet_extraction
```

**What gets tracked:**
- Extraction requests per user
- Success/failure rates
- Processing times
- Cost estimates
- Methods used
- Error patterns

**Query example:**
```javascript
// MongoDB query to get user stats
db.extraction_logs.aggregate([
  { $group: {
      _id: "$user_id",
      total_requests: { $sum: 1 },
      avg_processing_time: { $avg: "$processing_time_ms" },
      total_cost: { $sum: "$cost_estimate_usd" }
  }}
])
```

---

#### "Integration with frontend app"

**Recommended flow (async mode):**
   ```javascript
   // Submit job
   const submitResponse = await fetch('/api/v1/jobs/submit', {
     method: 'POST',
     body: formData
   });
   const { job_id } = await submitResponse.json();
   
   // Poll for status
   const pollInterval = setInterval(async () => {
     const statusResponse = await fetch(`/api/v1/jobs/${job_id}/status`);
     const status = await statusResponse.json();
     
     if (status.status === 'completed') {
       clearInterval(pollInterval);
       const result = await fetch(`/api/v1/jobs/${job_id}/result`);
       const data = await result.json();
       console.log(data);
     }
   }, 2000); // Poll every 2 seconds
   ```

---

## Troubleshooting

### "Tesseract not found"
Make sure tesseract is installed and in PATH:
```bash
tesseract --version
```

### "Google API key not configured"
Either:
1. Set `GOOGLE_API_KEY` in `.env` file
2. Or pass `apikey` parameter in request

### "Empty subjects array"
- Make sure image is clear and readable
- Try uploading higher resolution image
- Check if OCR is working: look at `extract/ocr_*.txt` files

---

## Can be improved

- [ ] Add support for Openai GPT-4 Vision
- [ ] Add more test cases
- [ ] Support for handwritten marksheets
- [ ] Using sinario background job
- [ ] Add caching for repeated requests
- [x] Rate limiting (implemented via slowapi)

---
