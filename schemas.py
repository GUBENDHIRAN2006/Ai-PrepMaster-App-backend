from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# --- Auth & User Schemas ---
class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    is_admin: Optional[bool] = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- User Settings & Profile Schemas ---
class ProfileOut(BaseModel):
    id: int
    user_id: int
    image: Optional[str] = None
    bio: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    bio: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


# --- Coding Challenges (DB-backed) ---
class ChallengeCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., description="Arrays, Strings, Linked Lists, Stack, Queue, Trees, Graphs, Dynamic Programming")
    difficulty: str = Field(..., description="Easy, Medium, Hard")
    prompt: str
    sample_input: str
    sample_output: str
    constraints: str

class ChallengeOut(BaseModel):
    id: int
    title: str
    category: str
    difficulty: str
    prompt: str
    sample_input: str
    sample_output: str
    constraints: str
    created_at: datetime

    class Config:
        from_attributes = True

class SubmissionSubmit(BaseModel):
    code: str

class SubmissionOut(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    code: str
    score: int
    feedback: Optional[str] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


# --- Chat History Schemas ---
class ChatCreate(BaseModel):
    message: str
    response: str

class ChatOut(BaseModel):
    id: int
    user_id: int
    message: str
    response: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Resume Upload Schemas ---
class ResumeOut(BaseModel):
    id: int
    user_id: int
    resume_path: str
    ats_score: int
    skills_found: Optional[str] = None
    missing_skills: Optional[str] = None
    feedback: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


# --- Interview Question Generator (Legacy compatible schemas) ---
class InterviewGenerateRequest(BaseModel):
    role: str
    experience: str
    difficulty: str

class QuestionOut(BaseModel):
    id: int
    question: str
    role: str
    difficulty: str
    experience: str
    sample_answer: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AnswerSubmitRequest(BaseModel):
    question_id: int
    answer: str

class AnswerEvaluationOut(BaseModel):
    id: int
    question: str
    answer: str
    sample_answer: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[int] = None

    class Config:
        from_attributes = True


# --- Dashboard & Activity Schemas ---
class ActivityLog(BaseModel):
    type: str # 'interview', 'challenge', 'resume'
    title: str
    score: Optional[int] = None
    date: datetime

class DashboardStats(BaseModel):
    total_interviews: int
    challenges_completed: int
    average_score: float
    resume_score: int
    recent_activity: List[ActivityLog]


# --- Admin Panels Schemas ---
class AdminUserDetail(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    created_at: datetime
    interviews_taken: int
    challenges_solved: int

class AdminChallengeSummary(BaseModel):
    id: int
    title: str
    category: str
    difficulty: str
    total_submissions: int

class AdminAnalytics(BaseModel):
    total_users: int
    total_challenges: int
    total_submissions: int
    total_interviews: int
    avg_score: float


# --- Career Guidance Schemas ---
class CareerRecommendRequest(BaseModel):
    experience: str = Field(..., description="Fresher, 1-2 years, 3-5 years, 5+ years")
    skills: List[str] = Field(..., description="List of known skills e.g. ['Python', 'React', 'SQL']")
    education: str = Field(..., description="Highest education level / field")
    interests: Optional[str] = Field(None, description="Job interests or preferred industries")

class CareerJobRole(BaseModel):
    company: str
    role: str
    match_score: int  # 0-100
    industry: str
    reason: str
    skills_needed: List[str]

class CareerRecommendOut(BaseModel):
    recommendations: List[CareerJobRole]
    summary: str
