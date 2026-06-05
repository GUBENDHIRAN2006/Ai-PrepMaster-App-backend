from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import uvicorn
import os
import shutil
import json

import models
import schemas
from database import engine, get_db, is_sqlite
from config import settings
from auth import hash_password, verify_password, create_access_token, get_current_user
import ai

# Create directories for static assets
os.makedirs("static/avatars", exist_ok=True)
os.makedirs("static/resumes", exist_ok=True)

# Initialize DB tables
models.Base.metadata.create_all(bind=engine)

# Pre-populate coding challenges and admin user on startup
db_session = next(get_db())
try:
    challenge_count = db_session.query(models.Challenge).count()
    if challenge_count == 0:
        challenges = [
            models.Challenge(
                title="Two Sum",
                category="Arrays",
                difficulty="Easy",
                prompt="Write a function `two_sum(nums: list, target: int) -> list` that returns indices of the two numbers such that they add up to the target. You may assume that each input would have exactly one solution.\n\nExample:\nInput: nums = [2,7,11,15], target = 9\nOutput: [0,1]",
                sample_input="nums = [2,7,11,15], target = 9",
                sample_output="[0,1]",
                constraints="2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9"
            ),
            models.Challenge(
                title="Valid Parentheses",
                category="Stack",
                difficulty="Easy",
                prompt="Write a function `is_valid(s: str) -> bool` that determines if the input string containing characters '(', ')', '{', '}', '[' and ']' is valid. Bracket sequences must be closed in the correct order.\n\nExample:\nInput: s = \"()[]{}\"\nOutput: True",
                sample_input="s = \"()[]{}\"",
                sample_output="True",
                constraints="1 <= s.length <= 10^4\ns consists of parentheses only '()[]{}'."
            ),
            models.Challenge(
                title="Reverse a Linked List",
                category="Linked Lists",
                difficulty="Medium",
                prompt="Write a function/method to reverse a singly linked list in-place and return the new head node. Provide code structure with node representation.",
                sample_input="head = [1,2,3,4,5]",
                sample_output="[5,4,3,2,1]",
                constraints="The number of nodes in the list is the range [0, 5000].\n-5000 <= Node.val <= 5000"
            ),
            models.Challenge(
                title="Binary Tree Level Order Traversal",
                category="Trees",
                difficulty="Medium",
                prompt="Write a function `level_order(root) -> list` that returns the level order traversal of its nodes' values (i.e. from left to right, level by level).",
                sample_input="root = [3,9,20,null,null,15,7]",
                sample_output="[[3],[9,20],[15,7]]",
                constraints="The number of nodes in the tree is in the range [0, 2000].\n-1000 <= Node.val <= 1000"
            )
        ]
        for c in challenges:
            db_session.add(c)
            
    # Auto create admin user if it does not exist
    admin_user = db_session.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL).first()
    if not admin_user:
        db_session.add(models.User(
            name="System Administrator",
            email=settings.ADMIN_EMAIL,
            password=hash_password(settings.ADMIN_PASSWORD),
            is_admin=True
        ))
    db_session.commit()
except Exception as e:
    print(f"Startup database seeding failed: {e}")
finally:
    db_session.close()

# Print database connection status to console
if is_sqlite:
    print("\n⚠️  WARNING: Running with local SQLite database (interview_prep.db).")
    print("   Changes to questions or challenges will NOT persist on hosted deployments.")
    print("   Please configure 'DATABASE_URL' to point to your Supabase PostgreSQL database in production.\n")
else:
    print("\n✅ Successfully connected to Supabase / PostgreSQL database.\n")

app = FastAPI(title="AI Interview Prep API", version="2.0.0")

# Enable CORS
origins = [org.strip() for org in settings.ALLOWED_ORIGINS.split(",") if org.strip()]

# Add newly deployed Vercel domains explicitly to allow_origins
extra_origins = [
    "https://frontend-five-delta-52.vercel.app",
    "https://frontend-fh7q370ok-gubendhiran-s-projects.vercel.app"
]
for o in extra_origins:
    if o not in origins:
        origins.append(o)

# Filter out '*' if allow_credentials is True to prevent FastAPI startup crash
if "*" in origins:
    origins = [o for o in origins if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder to serve uploaded files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount frontend compiled assets dynamically if they exist
dist_assets = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "assets"))
if os.path.exists(dist_assets):
    app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")


# --- ADMIN CONTROL DEPENDENCY ---
def get_current_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required to access this resource"
        )
    return current_user


# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Secure hash password
    hashed = hash_password(user_data.password)
    
    # Secure registration: by default, all new registrations are candidates.
    # Admin privileges are only granted if the email matches the ADMIN_EMAIL setting.
    is_admin = False
    if user_data.email.lower() == settings.ADMIN_EMAIL.lower():
        is_admin = True
        
    db_user = models.User(
        name=user_data.name,
        email=user_data.email,
        password=hashed,
        is_admin=is_admin
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Initialize profile
    db_profile = models.Profile(user_id=db_user.id, bio="", github="", linkedin="")
    db.add(db_profile)
    db.commit()
    
    return db_user

@app.post("/api/auth/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


# --- USER PROFILE & SETTINGS ENDPOINTS ---

@app.get("/api/profile", response_model=schemas.ProfileOut)
def get_profile(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id, bio="", github="", linkedin="")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@app.put("/api/profile", response_model=schemas.ProfileOut)
def update_profile(profile_data: schemas.ProfileUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)

    if profile_data.bio is not None:
        profile.bio = profile_data.bio
    if profile_data.github is not None:
        profile.github = profile_data.github
    if profile_data.linkedin is not None:
        profile.linkedin = profile_data.linkedin
        
    db.commit()
    db.refresh(profile)
    return profile

@app.post("/api/profile/upload-image")
def upload_profile_image(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)

    # Validate image file type extension
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() not in [".jpg", ".jpeg", ".png", ".gif"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Upload .jpg, .png, or .gif"
        )
        
    # Save file to disk
    filename = f"avatar_{current_user.id}{file_ext}"
    file_path = os.path.join("static", "avatars", filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Save relative route path in DB
    profile.image = f"/static/avatars/{filename}"
    db.commit()
    return {"image_url": profile.image}

@app.put("/api/profile/change-password")
def change_password(pass_data: schemas.PasswordChange, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify current password
    if not verify_password(pass_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
        
    # Hash and save new password
    current_user.password = hash_password(pass_data.new_password)
    db.commit()
    return {"detail": "Password successfully updated"}


# --- DB-BACKED CODING CHALLENGES ENDPOINTS ---

@app.get("/api/challenges", response_model=List[schemas.ChallengeOut])
def get_challenges(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Challenge).all()

@app.get("/api/challenges/{challenge_id}", response_model=schemas.ChallengeOut)
def get_challenge(challenge_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    chal = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return chal

@app.post("/api/challenges/{challenge_id}/submit", response_model=schemas.SubmissionOut)
def submit_challenge(challenge_id: int, payload: schemas.SubmissionSubmit, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    chal = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    # Grade code via AI module
    evaluation = ai.evaluate_code(chal.title, "Python/JavaScript", payload.code)
    
    # Save submission record in database
    db_sub = models.Submission(
        user_id=current_user.id,
        challenge_id=challenge_id,
        code=payload.code,
        score=evaluation.get("score", 0),
        feedback=evaluation.get("feedback", "")
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

@app.get("/api/challenges/submissions/history", response_model=List[schemas.SubmissionOut])
def get_submissions_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Submission).filter(models.Submission.user_id == current_user.id).order_by(models.Submission.submitted_at.desc()).all()


# --- CONTEXT-PRESERVING CHATBOT ENDPOINTS ---

@app.get("/api/chatbot/history", response_model=List[schemas.ChatOut])
def get_chatbot_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Chat).filter(models.Chat.user_id == current_user.id).order_by(models.Chat.created_at.asc()).all()

@app.post("/api/chatbot/chat")
def chat_mock_bot(payload: dict, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_message = payload.get("message", "")
    role = payload.get("role", "Python Developer")
    experience = payload.get("experience", "Fresher")
    difficulty = payload.get("difficulty", "Medium")
    
    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Empty chat message")
        
    # Read past chat context from database logs
    past_logs = db.query(models.Chat).filter(models.Chat.user_id == current_user.id).order_by(models.Chat.created_at.asc()).all()
    
    # Construct context messages for OpenAI
    chat_context = []
    for log in past_logs:
        chat_context.append({"role": "user", "content": log.message})
        chat_context.append({"role": "assistant", "content": log.response})
        
    # Append latest message
    chat_context.append({"role": "user", "content": user_message})
    
    # Query AI responder
    response_content = ai.chat_mock_interviewer(
        messages=chat_context,
        role=role,
        experience=experience,
        difficulty=difficulty
    )
    
    # Save the exchange to DB
    db_chat = models.Chat(
        user_id=current_user.id,
        message=user_message,
        response=response_content
    )
    db.add(db_chat)
    db.commit()
    
    return {"response": response_content}

@app.delete("/api/chatbot/reset")
def reset_chatbot_context(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.Chat).filter(models.Chat.user_id == current_user.id).delete()
    db.commit()
    return {"detail": "Chat history context successfully cleared"}


# --- PDF RESUME ANALYZER ENDPOINTS ---

@app.post("/api/resume/analyze-pdf", response_model=schemas.ResumeOut)
def analyze_pdf_resume(
    file: UploadFile = File(...),
    target_role: str = Form("Python Developer"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate PDF content extension type
    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported for upload resume parsing."
        )

    # Save PDF locally
    filename = f"resume_{current_user.id}_{int(func.now().scale if hasattr(func.now(), 'scale') else 12345678)}{file_ext}"
    file_path = os.path.join("static", "resumes", filename)
    
    file_content_bytes = file.file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(file_content_bytes)
        
    # Extract text from PDF
    extracted_text = ai.extract_text_from_pdf(file_content_bytes)
    
    # NLP processing and scoring
    analysis = ai.analyze_resume_pdf_nlp(extracted_text, target_role)
    
    # Save resume logs in database
    db_resume = models.Resume(
        user_id=current_user.id,
        resume_path=f"/static/resumes/{filename}",
        ats_score=analysis.get("score", 70),
        skills_found=json.dumps(analysis.get("skills_found", [])),
        missing_skills=json.dumps(analysis.get("missing_skills", [])),
        feedback=analysis.get("feedback", "")
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    return db_resume

@app.get("/api/resume/history", response_model=List[schemas.ResumeOut])
def get_resume_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Resume).filter(models.Resume.user_id == current_user.id).order_by(models.Resume.uploaded_at.desc()).all()


# --- INTERVIEW QUESTIONS GENERATOR ---

@app.post("/api/interviews/generate", response_model=List[schemas.QuestionOut])
def generate_interview(request: schemas.InterviewGenerateRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw_data = ai.generate_questions(role=request.role, experience=request.experience, difficulty=request.difficulty)
    tech_questions = raw_data.get("technical", [])
    hr_questions = raw_data.get("hr", [])
    
    saved_questions = []
    
    for q_item in tech_questions:
        db_question = models.InterviewQuestion(
            user_id=current_user.id,
            role=request.role,
            experience=request.experience,
            difficulty=request.difficulty,
            question=q_item.get("question", ""),
            sample_answer=q_item.get("sample_answer", "")
        )
        db.add(db_question)
        saved_questions.append(db_question)
        
    for q_item in hr_questions:
        db_question = models.InterviewQuestion(
            user_id=current_user.id,
            role=request.role,
            experience=request.experience,
            difficulty=request.difficulty,
            question=q_item.get("question", ""),
            sample_answer=q_item.get("sample_answer", "")
        )
        db.add(db_question)
        saved_questions.append(db_question)
        
    db.commit()
    for q in saved_questions:
        db.refresh(q)
        
    return saved_questions

@app.get("/api/interviews/history", response_model=List[schemas.AnswerEvaluationOut])
def get_interview_history(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.InterviewQuestion).filter(models.InterviewQuestion.user_id == current_user.id).order_by(models.InterviewQuestion.created_at.desc()).all()

@app.post("/api/interviews/submit-answer", response_model=schemas.AnswerEvaluationOut)
def submit_answer(request: schemas.AnswerSubmitRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_question = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.id == request.question_id,
        models.InterviewQuestion.user_id == current_user.id
    ).first()
    
    if not db_question:
        raise HTTPException(status_code=404, detail="Interview question not found")
        
    evaluation = ai.evaluate_user_answer(db_question.question, request.answer)
    
    db_question.answer = request.answer
    db_question.score = evaluation.get("score", 0)
    db_question.feedback = evaluation.get("feedback", "")
    
    db.commit()
    db.refresh(db_question)
    return db_question


# --- DASHBOARD & ANALYTICS STATS ---

@app.get("/api/dashboard/stats", response_model=schemas.DashboardStats)
def get_dashboard_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    
    # 1. Total Interviews Taken:
    distinct_interviews = db.query(
        models.InterviewQuestion.role,
        models.InterviewQuestion.difficulty,
        models.InterviewQuestion.experience
    ).filter(
        models.InterviewQuestion.user_id == user_id
    ).distinct().count()
    
    # 2. Coding Challenges Completed:
    challenges_count = db.query(models.Submission).filter(
        models.Submission.user_id == user_id
    ).count()
    
    # 3. Average Score calculation:
    iq_avg = db.query(func.avg(models.InterviewQuestion.score)).filter(
        models.InterviewQuestion.user_id == user_id,
        models.InterviewQuestion.score.isnot(None)
    ).scalar() or 0.0
    
    cc_avg = db.query(func.avg(models.Submission.score)).filter(
        models.Submission.user_id == user_id,
        models.Submission.score.isnot(None)
    ).scalar() or 0.0
    
    if iq_avg > 0 and cc_avg > 0:
        avg_score = round((iq_avg + cc_avg) / 2, 1)
    elif iq_avg > 0:
        avg_score = round(iq_avg, 1)
    elif cc_avg > 0:
        avg_score = round(cc_avg, 1)
    else:
        avg_score = 0.0
        
    # 4. Resume Score:
    latest_resume = db.query(models.Resume).filter(
        models.Resume.user_id == user_id
    ).order_by(models.Resume.uploaded_at.desc()).first()
    resume_score = latest_resume.ats_score if latest_resume else 0
    
    # 5. Recent Activity:
    iq_activities = db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.user_id == user_id,
        models.InterviewQuestion.answer.isnot(None)
    ).order_by(models.InterviewQuestion.created_at.desc()).limit(5).all()
    
    cc_activities = db.query(models.Submission).filter(
        models.Submission.user_id == user_id
    ).order_by(models.Submission.submitted_at.desc()).limit(5).all()
    
    res_activities = db.query(models.Resume).filter(
        models.Resume.user_id == user_id
    ).order_by(models.Resume.uploaded_at.desc()).limit(5).all()
    
    activities = []
    for iq in iq_activities:
        activities.append(schemas.ActivityLog(
            type="interview",
            title=f"Answered: {iq.role} ({iq.difficulty})",
            score=iq.score,
            date=iq.created_at
        ))
        
    for cc in cc_activities:
        chal_title = db.query(models.Challenge.title).filter(models.Challenge.id == cc.challenge_id).scalar() or "Coding Task"
        activities.append(schemas.ActivityLog(
            type="challenge",
            title=f"Solved Challenge: {chal_title}",
            score=cc.score,
            date=cc.submitted_at
        ))
        
    for res in res_activities:
        filename = os.path.basename(res.resume_path)
        activities.append(schemas.ActivityLog(
            type="resume",
            title=f"Uploaded Resume: {filename}",
            score=res.ats_score,
            date=res.uploaded_at
        ))
        
    activities.sort(key=lambda x: x.date, reverse=True)
    recent_activity = activities[:6]
    
    return schemas.DashboardStats(
        total_interviews=distinct_interviews,
        challenges_completed=challenges_count,
        average_score=float(avg_score),
        resume_score=resume_score,
        recent_activity=recent_activity
    )


# --- ADMIN CONTROL ENDPOINTS ---

@app.get("/api/admin/check-openai")
def get_check_openai(admin_user: models.User = Depends(get_current_admin)):
    """
    Tests the validity of the OpenAI API credentials connection.
    """
    is_active = ai.check_openai_key()
    return {"openai_active": is_active}

@app.get("/api/admin/users", response_model=List[schemas.AdminUserDetail])
def admin_get_users(admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    details = []
    for u in users:
        interviews = db.query(models.InterviewQuestion).filter(
            models.InterviewQuestion.user_id == u.id,
            models.InterviewQuestion.answer.isnot(None)
        ).count()
        
        challenges = db.query(models.Submission).filter(
            models.Submission.user_id == u.id
        ).count()
        
        details.append(schemas.AdminUserDetail(
            id=u.id,
            name=u.name,
            email=u.email,
            is_admin=u.is_admin,
            created_at=u.created_at,
            interviews_taken=interviews,
            challenges_solved=challenges
        ))
    return details

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot self-delete administrator accounts.")
        
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User account not found.")
        
    db.delete(user_to_delete)
    db.commit()
    return {"detail": "User account successfully moderated/removed."}

@app.post("/api/admin/challenges", response_model=schemas.ChallengeOut)
def admin_create_challenge(payload: schemas.ChallengeCreate, admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    db_chal = models.Challenge(
        title=payload.title,
        category=payload.category,
        difficulty=payload.difficulty,
        prompt=payload.prompt,
        sample_input=payload.sample_input,
        sample_output=payload.sample_output,
        constraints=payload.constraints
    )
    db.add(db_chal)
    db.commit()
    db.refresh(db_chal)
    return db_chal

@app.put("/api/admin/challenges/{challenge_id}", response_model=schemas.ChallengeOut)
def admin_update_challenge(challenge_id: int, payload: dict, admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    chal = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    if "title" in payload: chal.title = payload["title"]
    if "category" in payload: chal.category = payload["category"]
    if "difficulty" in payload: chal.difficulty = payload["difficulty"]
    if "prompt" in payload: chal.prompt = payload["prompt"]
    if "sample_input" in payload: chal.sample_input = payload["sample_input"]
    if "sample_output" in payload: chal.sample_output = payload["sample_output"]
    if "constraints" in payload: chal.constraints = payload["constraints"]
    
    db.commit()
    db.refresh(chal)
    return chal

@app.delete("/api/admin/challenges/{challenge_id}")
def admin_delete_challenge(challenge_id: int, admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    chal = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    db.delete(chal)
    db.commit()
    return {"detail": "Challenge successfully removed."}

@app.get("/api/admin/analytics", response_model=schemas.AdminAnalytics)
def admin_get_analytics(admin_user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_users = db.query(models.User).count()
    total_challenges = db.query(models.Challenge).count()
    total_submissions = db.query(models.Submission).count()
    
    total_interviews = db.query(
        models.InterviewQuestion.role,
        models.InterviewQuestion.difficulty,
        models.InterviewQuestion.user_id
    ).distinct().count()
    
    iq_avg = db.query(func.avg(models.InterviewQuestion.score)).filter(models.InterviewQuestion.score.isnot(None)).scalar() or 0.0
    cc_avg = db.query(func.avg(models.Submission.score)).filter(models.Submission.score.isnot(None)).scalar() or 0.0
    avg = round((iq_avg + cc_avg) / 2, 1) if (iq_avg > 0 and cc_avg > 0) else round(iq_avg + cc_avg, 1)
    
    return schemas.AdminAnalytics(
        total_users=total_users,
        total_challenges=total_challenges,
        total_submissions=total_submissions,
        total_interviews=total_interviews,
        avg_score=float(avg)
    )


# --- CAREER GUIDANCE ENDPOINT ---

@app.post("/api/career/recommend", response_model=schemas.CareerRecommendOut)
def career_recommend(
    request: schemas.CareerRecommendRequest,
    current_user: models.User = Depends(get_current_user)
):
    """
    Takes a candidate's experience, skills, education, and interests,
    and returns AI-powered company and role recommendations.
    """
    result = ai.get_career_recommendations(
        experience=request.experience,
        skills=request.skills,
        education=request.education,
        interests=request.interests or ""
    )
    # Normalise the response into the schema
    recommendations = [
        schemas.CareerJobRole(
            company=r.get("company", ""),
            role=r.get("role", ""),
            match_score=int(r.get("match_score", 70)),
            industry=r.get("industry", "Technology"),
            reason=r.get("reason", ""),
            skills_needed=r.get("skills_needed", [])
        )
        for r in result.get("recommendations", [])
    ]
    return schemas.CareerRecommendOut(
        recommendations=recommendations,
        summary=result.get("summary", "")
    )


# --- FRONTEND ROUTING FALLBACKS ---


from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def read_root():
    # If a frontend build index.html exists, serve it
    dist_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "index.html"))
    if os.path.exists(dist_index):
        try:
            with open(dist_index, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        except Exception:
            pass
            
    # Otherwise, return a premium landing page pointing the user to the correct ports
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Interview Prep Platform - Backend</title>
        <style>
            body {
                background: #0f172a;
                color: #f8fafc;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background-image: 
                    radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                    radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.12) 0px, transparent 50%);
            }
            .card {
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 20px;
                padding: 3rem;
                max-width: 550px;
                text-align: center;
                box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4);
                backdrop-filter: blur(20px);
            }
            .logo-icon {
                background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
                width: 64px;
                height: 64px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                color: white;
                font-size: 1.75rem;
                margin: 0 auto 1.5rem;
                box-shadow: 0 8px 20px rgba(139, 92, 246, 0.3);
            }
            h1 {
                font-size: 1.8rem;
                font-weight: 800;
                background: linear-gradient(135deg, #a78bfa 0%, #ec4899 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.75rem;
                letter-spacing: -0.025em;
            }
            p {
                color: #94a3b8;
                font-size: 0.95rem;
                line-height: 1.6;
                margin-bottom: 2.25rem;
            }
            .btn-group {
                display: flex;
                gap: 1rem;
                justify-content: center;
            }
            .btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
                color: white;
                padding: 0.85rem 1.75rem;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                font-size: 0.95rem;
                box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(139, 92, 246, 0.6);
            }
            .btn-secondary {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: #f8fafc;
                box-shadow: none;
            }
            .btn-secondary:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.2);
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="logo-icon">AI</div>
            <h1>PrepMaster Server Active</h1>
            <p>The FastAPI backend is running successfully on port 8000. To access the platform web interface, please visit the frontend development port (5173) or view the interactive API docs.</p>
            <div class="btn-group">
                <a href="http://localhost:5173" class="btn">Go to Platform (Port 5173)</a>
                <a href="/docs" class="btn btn-secondary">API Docs (Port 8000)</a>
            </div>
        </div>
    </body>
    </html>
    """, status_code=200)

@app.get("/{catchall:path}", response_class=HTMLResponse)
def serve_frontend_spa_fallback(catchall: str):
    # Skip routing API paths or Docs to frontend SPA
    if catchall.startswith("api/") or catchall.startswith("docs") or catchall.startswith("redoc") or catchall.startswith("openapi.json") or catchall.startswith("static/"):
        raise HTTPException(status_code=404, detail="API route not found")
        
    # Attempt to serve frontend build index.html
    dist_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "index.html"))
    if os.path.exists(dist_index):
        try:
            with open(dist_index, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        except Exception:
            pass
            
    # Fallback to the friendly landing redirection page
    return read_root()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
