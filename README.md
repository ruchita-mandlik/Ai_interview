# InterviewAI — AI Interview Preparation Assistant

> **"Prepare smarter. Interview better."**
> Practice with AI-powered interview questions, get instant evaluation and personalized feedback to boost your confidence and ace your next tech interview.

---

## 📌 Project Overview
**InterviewAI** is a full-stack, enterprise-grade AI mock interview platform designed for software engineers, developers, and candidates. The platform dynamically generates role-specific interview questions using Cloud Generative AI APIs, evaluates candidate answers using a 5-dimension rubric, computes weighted scores, provides actionable feedback, and tracks progress over time on a dynamic SaaS dashboard.

---

## ✨ Features
1. **User Authentication & Authorization**: Secure account registration and login using JWT tokens and bcrypt password hashing.
2. **Candidate Profile Management**: Tailor interview question generation to target role, experience level, education, and technical skills.
3. **Adaptive AI Question Generation**: Cloud GenAI API prompt engine generating questions tailored by topic, role, and difficulty.
4. **Weighted Answer Evaluation Rubric**:
   - Technical Correctness (35%)
   - Conceptual Completeness (25%)
   - Response Relevance (15%)
   - Structural Clarity (15%)
   - Depth of Understanding (10%)
5. **Detailed Interview Results & Model Answers**: Score breakdown, key strengths, areas for improvement, AI commentary, and ideal model answers.
6. **Dynamic Dashboard & Analytics**: Dynamic stats calculation directly from database records (no hardcoded fake values).
7. **Performance Analytics & Skill Mastery**: Tracks score trends over time and breaks down mastery level by technical skill.
8. **Interview History**: Searchable history log of all past interviews with instant report viewing.

---

## 🛠️ Technology Stack
- **Frontend**: HTML5, CSS3 (Vanilla CSS with CSS Variables & Glassmorphism design), JavaScript (ES6+ Fetch API, Async/Await), Responsive SaaS Layout.
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy ORM, Pydantic v2 schemas.
- **Database**: PostgreSQL (with automatic SQLite fallback for zero-config out-of-the-box local execution).
- **AI Integration**: Cloud Generative AI API (Google Gemini / Groq API) configurable via `.env`.
- **Testing**: Pytest & FastAPI TestClient.

---

## 📂 Project Structure
```
Ai_Interview/
├── backend/
│   ├── config/
│   │   └── settings.py
│   ├── database/
│   │   ├── database.py
│   │   └── init_db.py
│   ├── models/
│   │   ├── user.py
│   │   ├── candidate_profile.py
│   │   ├── interview.py
│   │   ├── question.py
│   │   ├── answer.py
│   │   └── evaluation.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── profile.py
│   │   ├── interview.py
│   │   ├── answer.py
│   │   └── evaluation.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── profile.py
│   │   ├── interviews.py
│   │   ├── evaluation.py
│   │   ├── dashboard.py
│   │   └── performance.py
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── interview_service.py
│   │   └── dashboard_service.py
│   ├── utils/
│   │   ├── security.py
│   │   └── validators.py
│   ├── prompts/
│   │   ├── question_generation.txt
│   │   ├── answer_evaluation.txt
│   │   └── feedback.txt
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   └── test_interview.py
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   └── .env.example
├── frontend/
│   ├── css/
│   │   ├── style.css
│   │   ├── auth.css
│   │   ├── dashboard.css
│   │   └── interview.css
│   ├── js/
│   │   ├── api.js
│   │   ├── auth.js
│   │   ├── dashboard.js
│   │   ├── interview-config.js
│   │   ├── interview.js
│   │   ├── result.js
│   │   ├── history.js
│   │   ├── performance.js
│   │   └── profile.js
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── dashboard.html
│   ├── interview-config.html
│   ├── interview.html
│   ├── result.html
│   ├── history.html
│   ├── performance.html
│   └── profile.html
└── README.md
```

---

## ⚙️ Prerequisites & Setup

### 1. Environment Configuration
Create `.env` file inside `backend/`:
```env
PORT=8000
HOST=0.0.0.0
ENV=development

SECRET_KEY=super_secret_jwt_key_2026_dev
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# PostgreSQL Database Connection
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ai_interview_db

# Cloud GenAI API
GENAI_API_KEY=your_genai_api_key_here
GENAI_MODEL=gemini-1.5-flash
```

### 2. PostgreSQL Setup
1. Create PostgreSQL database:
   ```sql
   CREATE DATABASE ai_interview_db;
   ```
2. Update `DATABASE_URL` in `backend/.env` with your PostgreSQL username and password.

---

## 🚀 Running the Application

### 1. Start the Backend API
```bash
# Navigate to backend
cd backend

# Activate Virtual Environment (Windows)
.\.venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt

# Initialize Database Tables
python -m backend.database.init_db

# Start FastAPI Server
uvicorn backend.main:app --reload --port 8000
```

### 2. Open Frontend
Open your browser at:
`http://localhost:8000/`

Interactive Swagger API Documentation:
`http://localhost:8000/docs`

---

## 🧪 Running Tests
```bash
.\backend\.venv\Scripts\python.exe -m pytest backend/tests
```

---

## 📝 License & Author
**InterviewAI** — AI Interview Preparation Assistant. Developed for production demonstration & technical assessment.
