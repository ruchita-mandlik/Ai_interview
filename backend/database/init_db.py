import logging
from backend.database.database import Base, engine
from backend.models.user import User
from backend.models.candidate_profile import CandidateProfile
from backend.models.interview import Interview
from backend.models.question import InterviewQuestion
from backend.models.answer import Answer
from backend.models.evaluation import Evaluation
from backend.models.resume_analysis import ResumeJDAnalysis
from backend.models.coding_interview import CodingInterview, CodingQuestion, CodingSubmission

from sqlalchemy import text

logger = logging.getLogger("uvicorn.error")

def init_db():
    logger.info("Creating database tables if not existing...")
    Base.metadata.create_all(bind=engine)
    
    # Ensure newly added columns exist in DB tables
    try:
        with engine.begin() as conn:
            if "postgresql" in str(engine.url):
                conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS adaptation_reason TEXT;"))
                conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS is_follow_up BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS parent_question_id VARCHAR;"))
                conn.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS resume_analysis_id VARCHAR;"))
                conn.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS mode VARCHAR DEFAULT 'text';"))
                conn.execute(text("ALTER TABLE interviews ADD COLUMN IF NOT EXISTS voice_name VARCHAR DEFAULT 'default';"))
                conn.execute(text("ALTER TABLE answers ADD COLUMN IF NOT EXISTS transcript_raw TEXT;"))
                conn.execute(text("ALTER TABLE answers ADD COLUMN IF NOT EXISTS is_voice_submission BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE answers ADD COLUMN IF NOT EXISTS audio_duration_seconds FLOAT;"))
                conn.execute(text("ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS communication_notes TEXT;"))
            else:
                # SQLite fallback
                for stmt in [
                    "ALTER TABLE interview_questions ADD COLUMN adaptation_reason TEXT;",
                    "ALTER TABLE interview_questions ADD COLUMN is_follow_up BOOLEAN DEFAULT 0;",
                    "ALTER TABLE interview_questions ADD COLUMN parent_question_id TEXT;",
                    "ALTER TABLE interviews ADD COLUMN resume_analysis_id TEXT;",
                    "ALTER TABLE interviews ADD COLUMN mode TEXT DEFAULT 'text';",
                    "ALTER TABLE interviews ADD COLUMN voice_name TEXT DEFAULT 'default';",
                    "ALTER TABLE answers ADD COLUMN transcript_raw TEXT;",
                    "ALTER TABLE answers ADD COLUMN is_voice_submission BOOLEAN DEFAULT 0;",
                    "ALTER TABLE answers ADD COLUMN audio_duration_seconds REAL;",
                    "ALTER TABLE evaluations ADD COLUMN communication_notes TEXT;"
                ]:
                    try:
                        conn.execute(text(stmt))
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Migration check warning: {e}")
        
    logger.info("Database tables initialized successfully.")


if __name__ == "__main__":
    init_db()

