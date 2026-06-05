from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(BigInteger, primary_key=True, index=True)
    name       = Column(String(255), nullable=False)
    email      = Column(String(255), unique=True, index=True, nullable=False)
    password   = Column(String(255), nullable=False)   # bcrypt hashed
    is_admin   = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    questions   = relationship("InterviewQuestion", back_populates="user", cascade="all, delete-orphan")
    challenges  = relationship("CodingChallenge",   back_populates="user", cascade="all, delete-orphan")
    resumes     = relationship("Resume",            back_populates="user", cascade="all, delete-orphan")
    profile     = relationship("Profile",           back_populates="user", uselist=False, cascade="all, delete-orphan")
    submissions = relationship("Submission",        back_populates="user", cascade="all, delete-orphan")
    chats       = relationship("Chat",              back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id      = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True)
    image   = Column(String(255), nullable=True)   # avatar file path
    bio     = Column(Text, nullable=True)
    github  = Column(String(255), nullable=True)
    linkedin= Column(String(255), nullable=True)

    user = relationship("User", back_populates="profile")


class Challenge(Base):
    __tablename__ = "challenges"

    id            = Column(BigInteger, primary_key=True, index=True)
    title         = Column(String(255), nullable=False)
    category      = Column(String(100), nullable=False)   # Arrays, Trees, DP…
    difficulty    = Column(String(50),  nullable=False)   # Easy, Medium, Hard
    prompt        = Column(Text,        nullable=False)
    sample_input  = Column(Text,        nullable=False)
    sample_output = Column(Text,        nullable=False)
    constraints   = Column(Text,        nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    submissions = relationship("Submission", back_populates="challenge", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id           = Column(BigInteger, primary_key=True, index=True)
    user_id      = Column(BigInteger, ForeignKey("users.id"),     nullable=False)
    challenge_id = Column(BigInteger, ForeignKey("challenges.id"),nullable=False)
    code         = Column(Text,    nullable=False)
    score        = Column(Integer, nullable=False)
    feedback     = Column(Text,    nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    user      = relationship("User",      back_populates="submissions")
    challenge = relationship("Challenge", back_populates="submissions")


class Resume(Base):
    __tablename__ = "resumes"

    id             = Column(BigInteger, primary_key=True, index=True)
    user_id        = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    resume_path    = Column(String(255), nullable=False)   # /static/resumes/...
    ats_score      = Column(Integer,     nullable=False)   # 0-100 ATS score
    skills_found   = Column(Text,        nullable=True)    # JSON array string
    missing_skills = Column(Text,        nullable=True)    # JSON array string
    feedback       = Column(Text,        nullable=True)
    uploaded_at    = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="resumes")


class Chat(Base):
    __tablename__ = "chats"

    id         = Column(BigInteger, primary_key=True, index=True)
    user_id    = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    message    = Column(Text, nullable=False)
    response   = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="chats")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id            = Column(BigInteger, primary_key=True, index=True)
    user_id       = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    role          = Column(String(255), nullable=False)
    experience    = Column(String(100), nullable=False)
    difficulty    = Column(String(50),  nullable=False)
    question      = Column(Text,        nullable=False)
    answer        = Column(Text,        nullable=True)
    sample_answer = Column(Text,        nullable=True)
    feedback      = Column(Text,        nullable=True)
    score         = Column(Integer,     nullable=True)   # 0-100 for dashboard
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="questions")


# Legacy table — kept for backward compatibility with old data
class CodingChallenge(Base):
    __tablename__ = "coding_challenges"

    id            = Column(BigInteger, primary_key=True, index=True)
    user_id       = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    title         = Column(String(255), nullable=False)
    difficulty    = Column(String(50),  nullable=False)
    prompt        = Column(Text,        nullable=False)
    solution_code = Column(Text,        nullable=True)
    language      = Column(String(50),  nullable=True)
    score         = Column(Integer,     nullable=True)
    feedback      = Column(Text,        nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="challenges")
