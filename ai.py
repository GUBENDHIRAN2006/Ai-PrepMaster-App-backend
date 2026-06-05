import json
import random
import io
import re
from openai import OpenAI
from config import settings
from PyPDF2 import PdfReader
import pdfplumber

# Initialize NLTK safely
import nltk
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    try:
        nltk.download('punkt', quiet=True)
    except Exception:
        print("Warning: NLTK download failed. Using regex fallback tokenizer.")

from dotenv import load_dotenv
import os

# Dynamically resolve client at runtime to pick up .env updates immediately
def get_openai_client():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            return OpenAI(api_key=api_key)
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI client: {e}")
    return None


# --- OPENAI KEY CHECKER ---
def check_openai_key() -> bool:
    """
    Checks if the configured OpenAI API key is valid by calling a lightweight model check.
    """
    client = get_openai_client()
    if not client:
        return False
    try:
        # Request models list which is cheap and tests auth
        client.models.list()
        return True
    except Exception as e:
        print(f"OpenAI validation connection failed: {e}")
        return False


# --- FALLBACK QUESTION DATA ---
FALLBACK_QUESTIONS = {
    "Python Developer": {
        "Technical": [
            "Explain the difference between a list and a tuple in Python, and when would you use each?",
            "What are decorators in Python? Write a simple custom decorator that logs execution time.",
            "How does memory management work in Python? What is reference counting and garbage collection?",
            "Explain Python's GIL (Global Interpreter Lock). How do you achieve true parallelism in Python?",
            "What is the difference between shallow copy and deep copy in Python? How do you create them?",
            "Explain the difference between `__init__` and `__new__` magic methods.",
            "How do generator functions work in Python? What are the benefits of using generators?",
            "Describe how context managers work. How can you implement one using a class vs the `@contextmanager` decorator?",
            "What is list comprehension? Write a list comprehension that filters even numbers and squares them.",
            "How would you optimize a slow-running Python script dealing with heavy data manipulation?"
        ],
        "HR": [
            "Why do you want to work as a Python Developer at our company?",
            "Tell me about a challenging technical problem you solved using Python.",
            "How do you stay up-to-date with the latest PEP standards and Python releases?",
            "Describe a situation where you had a disagreement with a team member. How did you resolve it?",
            "Where do you see yourself in 3 years as a Python Developer?"
        ]
    },
    "Full Stack Developer": {
        "Technical": [
            "Explain the difference between client-side rendering (CSR) and server-side rendering (SSR).",
            "What is CORS (Cross-Origin Resource Sharing)? How do you configure it securely?",
            "Describe the standard flow of JWT-based authentication between client and server.",
            "How would you optimize the loading speed and performance of a modern React and Node.js application?",
            "What is database indexing? What are the pros and cons of over-indexing a table?",
            "Explain the difference between REST APIs and GraphQL. In what scenarios would you choose one over the other?",
            "How do WebSockets differ from HTTP poll connections, and how do they establish connections?",
            "What are CSS flexbox and grid layouts, and when would you choose one over the other?",
            "Explain the concept of Virtual DOM in React and how the reconciliation process works.",
            "How would you design a scalable microservices architecture for an e-commerce platform?"
        ],
        "HR": [
            "How do you balance learning both frontend and backend technologies in your career?",
            "Tell me about a full-stack project you built from scratch. What challenges did you face?",
            "How do you prioritize features when facing tight deadlines?",
            "Describe a time you had to deal with a severe production bug. What was your process?",
            "Why are you interested in a Full Stack role instead of specializing in just Frontend or Backend?"
        ]
    },
    "AI/ML Engineer": {
        "Technical": [
            "Explain the difference between supervised, unsupervised, and reinforcement learning.",
            "What is overfitting in machine learning? What techniques can you use to prevent it?",
            "Describe how backpropagation works in deep neural networks.",
            "What is the difference between L1 (Lasso) and L2 (Ridge) regularization?",
            "How does the self-attention mechanism work in Transformers?",
            "Explain the difference between precision, recall, and F1-score. When would you prioritize recall over precision?",
            "What is gradient descent? Explain the difference between SGD, Adam, and RMSprop optimizers.",
            "How do you handle highly imbalanced datasets when training a classifier?",
            "What are embeddings (e.g. text/image embeddings) and how are they used in Vector databases?",
            "How would you deploy a deep learning model to production while minimizing latency and inference costs?"
        ],
        "HR": [
            "What got you interested in the field of Artificial Intelligence and Machine Learning?",
            "How do you explain complex machine learning model decisions to non-technical business stakeholders?",
            "Tell me about a time when your ML model didn't perform well in production. How did you diagnose and fix it?",
            "How do you keep up with the rapid pace of AI research and new model releases?",
            "What is your approach to handling ethical considerations, such as bias, in AI models?"
        ]
    },
    "Data Analyst": {
        "Technical": [
            "What is the difference between inner join, left join, right join, and full outer join in SQL?",
            "Explain the difference between SELECT, WHERE, and HAVING clauses in SQL.",
            "What are window functions in SQL? Give an example of ROW_NUMBER() or DENSE_RANK().",
            "How do you handle missing or null values in a dataset using Pandas?",
            "Explain the difference between descriptive, predictive, and prescriptive analytics.",
            "What is A/B testing? How do you determine if the results of an A/B test are statistically significant?",
            "How do you create a dashboard in Tableau or PowerBI that effectively communicates key business metrics?",
            "What is data normalization and denormalization? When is each preferred?",
            "Explain the Central Limit Theorem and why it is important in statistical analysis.",
            "How would you identify outliers in a dataset, and what would you do with them?"
        ],
        "HR": [
            "Describe a time when you translated complex data analysis into actionable business strategy.",
            "How do you handle situations where stakeholders disagree with your data findings?",
            "Tell me about your favorite data visualization tool and why you prefer it.",
            "How do you ensure accuracy and double-check your analysis before presenting it?",
            "Why did you choose a career in Data Analytics?"
        ]
    },
    "Frontend Developer": {
        "Technical": [
            "Explain the component lifecycle in React (or useEffect hook dependency arrays).",
            "What is Redux or context-based state management? When should you use global state vs local state?",
            "Explain how the CSS Box Model works.",
            "Describe the difference between server-side rendering (SSR), static site generation (SSG), and incremental static regeneration (ISR).",
            "What is code splitting and lazy loading in React? How do they improve web performance?",
            "Explain event bubbling and event capturing in JavaScript.",
            "What is the difference between local storage, session storage, and cookies?",
            "How do you make a web application fully accessible (WCAG compliant) for screen readers?",
            "What is the difference between relative, absolute, fixed, and sticky positioning in CSS?",
            "How do React hooks (like useMemo and useCallback) work and when should you use them to optimize performance?"
        ],
        "HR": [
            "What makes a web interface 'good' or 'user-friendly' in your opinion?",
            "How do you handle feedback from UI/UX designers and adapt to design updates?",
            "Tell me about a time you had to optimize a frontend application that was lagging for users.",
            "What is your favorite CSS framework or method (Tailwind, CSS Modules, Styled Components) and why?",
            "How do you handle browser compatibility issues?"
        ]
    },
    "Backend Developer": {
        "Technical": [
            "What is REST? Describe the HTTP status code ranges (2xx, 3xx, 4xx, 5xx) and their standard meanings.",
            "Explain the difference between SQL and NoSQL databases. When would you choose NoSQL over SQL?",
            "What are database transactions? Explain ACID properties.",
            "Describe how database connection pooling works and why it is important for API scaling.",
            "What is a message broker (e.g. RabbitMQ, Kafka)? In what scenarios would you use one?",
            "How do you secure API endpoints? Explain rate limiting, sanitization, and HTTPS.",
            "What is N+1 query problem in ORMs, and how do you resolve it?",
            "How do you design a robust caching strategy using Redis?",
            "What is the difference between vertical scaling and horizontal scaling of backend servers?",
            "Explain the difference between synchronous execution and asynchronous execution in backend applications."
        ],
        "HR": [
            "Why do you prefer Backend development over Frontend development?",
            "Tell me about a time you designed a backend system database schema that had to handle complex relationships.",
            "How do you test your backend code (unit tests, integration tests, mock systems)?",
            "Describe a time when a server went down under high load. How did you react?",
            "What tools do you use to monitor backend health and API performance in production?"
        ]
    }
}


# --- INTERVIEW QUESTIONS GENERATOR ---
def generate_questions(role: str, experience: str, difficulty: str) -> dict:
    """
    Generates 10 Technical and 5 HR questions.
    Uses OpenAI if configured, otherwise falls back to local pre-defined questions.
    """
    if role not in FALLBACK_QUESTIONS:
        role = "Python Developer"
        
    client = get_openai_client()
    if client:
        prompt = f"""
        You are an expert interviewer. Generate a structured interview for a candidate applying for the role of '{role}' with '{experience}' experience. The difficulty level is '{difficulty}'.
        
        Generate exactly:
        - 10 Technical Questions with sample/model answers.
        - 5 HR/Behavioral Questions with sample/model answers.

        Format the response STRICTLY as a JSON object with this exact structure:
        {{
            "technical": [
                {{"question": "Question text here", "sample_answer": "Detailed model answer guidelines here"}}
            ],
            "hr": [
                {{"question": "Question text here", "sample_answer": "Detailed model answer guidelines here"}}
            ]
        }}
        
        Ensure questions are tailored to the role, difficulty, and experience level.
        Do not add any markdown, comments, or extra text. Only return the JSON.
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional HR and Technical Recruiter. You only output valid JSON code."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data
        except Exception as e:
            print(f"Error calling OpenAI API in generate_questions: {e}. Falling back to mock data.")

    # Fallback Implementation
    role_questions = FALLBACK_QUESTIONS.get(role, FALLBACK_QUESTIONS["Python Developer"])
    
    tech_list = []
    for q in role_questions["Technical"]:
        tech_list.append({
            "question": f"[{difficulty}] {q}",
            "sample_answer": f"This question tests knowledge regarding the technical aspects of '{role}'. A good answer should cover core components, code examples where applicable, and demonstrate clear understanding of the underlying principles."
        })
        
    hr_list = []
    for q in role_questions["HR"]:
        hr_list.append({
            "question": q,
            "sample_answer": "A strong response uses the STAR method (Situation, Task, Action, Result) to provide a clear, professional story showcasing teamwork, adaptability, or problem-solving skills."
        })
        
    return {
        "technical": tech_list,
        "hr": hr_list
    }


# --- ANSWER EVALUATION ---
def evaluate_user_answer(question: str, user_answer: str) -> dict:
    """
    Evaluates the user's answer to an interview question.
    Returns a score (0-100) and structured feedback.
    """
    if not user_answer or len(user_answer.strip()) < 10:
        return {
            "score": 10,
            "feedback": "Your answer is too short or empty. Please provide a more detailed response showing your technical logic and methodology."
        }

    client = get_openai_client()
    if client:
        prompt = f"""
        You are a hiring manager evaluating a candidate's answer to an interview question.
        
        Question: {question}
        Candidate's Answer: {user_answer}
        
        Evaluate the answer on:
        1. Accuracy and technical correctness.
        2. Depth of knowledge.
        3. Communication and clarity.
        
        Provide:
        - A numerical score from 0 to 100.
        - Constructive feedback highlighting strengths, weaknesses, and how to improve.
        
        Format the response STRICTLY as a JSON object:
        {{
            "score": 85,
            "feedback": "Your feedback comments go here..."
        }}
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional assessor. You only output valid JSON code."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.5
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data
        except Exception as e:
            print(f"Error calling OpenAI API in evaluate_user_answer: {e}. Falling back to mock calculation.")

    # Fallback Evaluation
    words_count = len(user_answer.split())
    if words_count < 20:
        base_score = random.randint(40, 55)
        feedback = "The answer is brief. To improve, structure your response by introducing the concept, giving a practical use case or coding context, and mentioning details on performance or trade-offs."
    elif words_count < 50:
        base_score = random.randint(60, 75)
        feedback = "Good start! Your response addresses the question. To reach an elite score, try to provide a structured explanation, use industry terms correctly, and elaborate on edge cases or personal project experiences."
    else:
        base_score = random.randint(78, 95)
        feedback = "Excellent effort! You have written a detailed and thorough response. You successfully covered the core concepts. Make sure to keep it structured and concise during real interviews."

    return {
        "score": base_score,
        "feedback": feedback
    }


# --- MOCK CHATBOT INTERVIEWER (Context-Preserving) ---
def chat_mock_interviewer(messages: list, role: str, experience: str, difficulty: str) -> str:
    """
    Maintains a conversation where the AI is the interviewer.
    `messages` is a list of dicts like: [{"role": "user"|"assistant", "content": "..."}]
    """
    system_prompt = f"""
    You are an expert technical interviewer conducting a mock interview for the role of '{role}' with '{experience}' experience. The difficulty of the interview is '{difficulty}'.
    
    Instructions:
    1. Act as a professional, encouraging, yet critical interviewer.
    2. Ask ONE question at a time.
    3. Evaluate the user's responses briefly, give a small tip or acknowledgement, and then ask the NEXT question.
    4. Start by introducing yourself and asking the first question (e.g. 'Tell me about yourself' or a basic technical question).
    5. After about 5-6 questions, wrap up the interview, give a summary score out of 100, and provide final feedback.
    """

    client = get_openai_client()
    if client:
        try:
            formatted_messages = [{"role": "system", "content": system_prompt}] + messages
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=formatted_messages,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenAI API in chat_mock_interviewer: {e}. Running local agent.")

    # Fallback Chatbot Logic
    user_msgs = [m for m in messages if m["role"] == "user"]
    
    if not user_msgs:
        return f"Hello! Welcome to your mock interview for the '{role}' position ({experience} / {difficulty}). I am your AI Interviewer today. Let's start with a warm-up: could you briefly introduce yourself and share what projects you have worked on recently?"
        
    num_exchanges = len(user_msgs)
    
    if num_exchanges == 1:
        return f"Nice to meet you! Let's dive into some technical aspects. For a {role}, how do you usually approach system design, and how do you ensure code readability and testability in your projects?"
    elif num_exchanges == 2:
        return f"Good approach. Let's do a role-specific question. In terms of {difficulty} complexity, can you explain how you handle concurrency, parallel threads, or asynchronous processing in your code?"
    elif num_exchanges == 3:
        return f"Interesting explanation. Let's move on to a situational scenario. Tell me about a time you had a critical bug in production. What were the steps you took to diagnose, fix, and post-mortem the issue?"
    elif num_exchanges == 4:
        return f"Handling production issues requires a calm head, and you seem to have a solid method. Let's ask one final behavioral question: How do you prioritize your daily task load when multiple high-priority requirements land on your plate simultaneously?"
    else:
        # Wrap up mock interview
        return f"Thank you for sharing that! That concludes our mock interview. Here is your summary feedback:\n\n" \
               f"**Overall Score:** 84/100\n\n" \
               f"**Strengths:** You demonstrated strong structural thinking, calm production incident handling, and clear communication.\n" \
               f"**Areas of Improvement:** Try to include more metric-focused results (e.g., 'reduced load time by 30%') when describing achievements.\n\n" \
               f"Good luck with your preparation!"


# --- CODING CHALLENGES EVALUATOR ---
def evaluate_code(title: str, language: str, solution_code: str) -> dict:
    """
    Evaluates the code submitted by the user for a challenge.
    """
    if not solution_code or len(solution_code.strip()) < 15:
        return {
            "score": 10,
            "feedback": "The submission is empty or too short. Please provide a functional code solution."
        }

    client = get_openai_client()
    if client:
        prompt = f"""
        You are a senior tech lead reviewing a code submission for a coding challenge.
        
        Challenge Title: {title}
        Programming Language: {language}
        Candidate's Code:
        ```
        {solution_code}
        ```
        
        Review the code for:
        1. Correctness and logic.
        2. Time and Space complexity.
        3. Readability and clean-code practices.
        
        Provide:
        - A score from 0 to 100.
        - Detailed feedback including performance hints, complexity analysis, and potential optimizations.
        
        Format the response STRICTLY as a JSON object:
        {{
            "score": 80,
            "feedback": "Review feedback markdown goes here..."
        }}
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a code reviewer. You output JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"Error in evaluate_code: {e}. Using fallback.")

    # Fallback Code Evaluator
    score = random.randint(70, 92)
    feedback = f"""### Code Review Feedback (Local Fallback)
    
* **Language Detected:** {language}
* **Estimated Complexity:** O(N) Time complexity, O(1) Auxiliary Space complexity.
* **Review Summary:**
  * Clean styling and indentation.
  * Correct implementation of loop logic / helper operations.
  * Good usage of standard language library methods.
  
* **Suggestions for Improvement:**
  * Consider adding input verification/handling for null or empty values.
  * You could optimize memory by lazy evaluation or avoiding extra array initializations.
"""
    return {
        "score": score,
        "feedback": feedback
    }


# --- PDF TEXT EXTRACTION UTILITY ---
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts plain text contents from PDF byte arrays.
    Uses pdfplumber with a robust PyPDF2 fallback.
    """
    text = ""
    # Try pdfplumber first
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber failed, attempting PyPDF2 fallback: {e}")
        # Try PyPDF2 fallback
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e2:
            print(f"PyPDF2 fallback also failed: {e2}")
            
    return text.strip()


# --- NLP SKILLS AND ATS ANALYZER ---
COMMON_TECH_SKILLS = [
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "ruby", "go", "rust", "php", "scala", "kotlin", "swift", "html", "css", "sql", "r",
    # Frameworks
    "react", "angular", "vue", "next.js", "node.js", "express", "django", "flask", "fastapi", "spring boot", "laravel", "rails", "asp.net", "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    # Cloud & DevOps
    "docker", "kubernetes", "aws", "azure", "gcp", "terraform", "jenkins", "git", "github", "gitlab", "ci/cd", "linux", "nginx",
    # Database
    "mysql", "postgresql", "mongodb", "sqlite", "redis", "elasticsearch"
]

def analyze_resume_pdf_nlp(resume_text: str, target_role: str = "Developer") -> dict:
    """
    Scans a resume for key technical skills and missing components using basic NLP token scanning.
    """
    if not resume_text or len(resume_text.strip()) < 30:
        return {
            "score": 15,
            "skills_found": [],
            "missing_skills": [],
            "feedback": "The uploaded document did not yield sufficient text. Make sure it is a text-accessible PDF and not a scanned image."
        }

    # NLP tokenization
    tokens = []
    try:
        tokens = nltk.word_tokenize(resume_text.lower())
    except Exception:
        # Regex fallback tokenizer
        tokens = re.findall(r'\b\w+\b', resume_text.lower())

    tokens_set = set(tokens)

    # Detect skills
    skills_found = [skill for skill in COMMON_TECH_SKILLS if skill in tokens_set]

    # Generate role target requirements
    role_targets = {
        "Python Developer": ["python", "django", "flask", "fastapi", "git", "sql", "docker"],
        "Full Stack Developer": ["react", "node.js", "javascript", "sql", "html", "css", "git", "docker"],
        "AI/ML Engineer": ["python", "tensorflow", "pytorch", "scikit-learn", "numpy", "pandas", "git"],
        "Data Analyst": ["sql", "python", "pandas", "numpy", "r", "excel", "git"],
        "Frontend Developer": ["javascript", "typescript", "react", "html", "css", "git", "vue", "angular"],
        "Backend Developer": ["python", "node.js", "sql", "docker", "fastapi", "aws", "kubernetes", "git"]
    }

    targets = role_targets.get(target_role, ["python", "javascript", "git", "sql"])
    missing_skills = [target for target in targets if target not in tokens_set]

    # Calculate basic ATS score
    matched_targets = len(targets) - len(missing_skills)
    ratio = matched_targets / len(targets) if targets else 1
    
    # Calculate additional points for extra skills
    bonus = min(len(skills_found) * 2, 20)
    
    ats_score = int((ratio * 70) + bonus + 10)
    ats_score = min(ats_score, 100)

    # Use OpenAI for more comprehensive grading if available
    client = get_openai_client()
    if client:
        try:
            prompt = f"""
            Analyze the following extracted resume text relative to the target role '{target_role}':
            
            ```
            {resume_text}
            ```

            Provide:
            1. An ATS compatibility score (0-100).
            2. Detailed Markdown feedback highlighting strengths, formatting errors, and action verb optimizations.
            
            Format response as JSON:
            {{
                "score": 82,
                "feedback": "Markdown text feedback here..."
            }}
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional ATS scanning algorithm. You output JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            analysis = json.loads(response.choices[0].message.content)
            return {
                "score": analysis.get("score", ats_score),
                "skills_found": skills_found,
                "missing_skills": missing_skills,
                "feedback": analysis.get("feedback", "Excellent resume structure.")
            }
        except Exception as e:
            print(f"OpenAI analysis failed, using local NLP logic: {e}")

    # Fallback Feedback formatting
    feedback = f"""### Resume ATS Scan Report (Local NLP Engine)
    
* **Target Role Analysis:** {target_role}
* **Score:** {ats_score}/100
* **Identified Keywords ({len(skills_found)}):** {", ".join([s.upper() for s in skills_found])}
* **Missing Target Keywords:** {", ".join([m.upper() for m in missing_skills]) if missing_skills else "None! Excellent alignment."}

#### Improvement Suggestions:
1. **Highlight Core Skills:** Integrate the missing keywords ({", ".join([m.upper() for m in missing_skills])}) directly into your work description bullet points.
2. **Quantify Accomplishments:** Focus on metrics (e.g. 'boosted system performance by 22%') rather than stating basic responsibilities.
3. **Format Readability:** Ensure no fancy graphic widgets or tables are present, as they can cause text parser failure.
"""

    return {
        "score": ats_score,
        "skills_found": skills_found,
        "missing_skills": missing_skills,
        "feedback": feedback
    }


# --- CAREER GUIDANCE & JOB RECOMMENDATIONS ---
CAREER_FALLBACK_DB = {
    "python": [
        {"company": "Google", "role": "Software Engineer (Python)", "industry": "Technology", "match_score": 92, "reason": "Google heavily uses Python for backend services, automation, and AI/ML pipelines. Your Python skills are a strong fit.", "skills_needed": ["Python", "Django/Flask", "SQL", "Docker"]},
        {"company": "Netflix", "role": "Backend Engineer", "industry": "Streaming / Entertainment", "match_score": 88, "reason": "Netflix's data and microservices layers rely on Python. Strong backend experience would be valued.", "skills_needed": ["Python", "FastAPI", "Kafka", "AWS"]},
        {"company": "Stripe", "role": "API Engineer", "industry": "FinTech", "match_score": 85, "reason": "Stripe's API infrastructure team builds developer-facing tools primarily in Python.", "skills_needed": ["Python", "REST APIs", "Databases", "Security"]},
        {"company": "Palantir", "role": "Software Developer", "industry": "Data Analytics", "match_score": 80, "reason": "Palantir uses Python extensively for data pipelines and analytical dashboards.", "skills_needed": ["Python", "Pandas", "SQL", "Cloud"]},
    ],
    "javascript": [
        {"company": "Meta", "role": "Frontend Engineer", "industry": "Social Media / Technology", "match_score": 91, "reason": "Meta's product UIs are React-based and JavaScript expertise is core to their frontend stack.", "skills_needed": ["React", "JavaScript", "TypeScript", "GraphQL"]},
        {"company": "Shopify", "role": "Full Stack Developer", "industry": "E-Commerce", "match_score": 87, "reason": "Shopify's merchant platform is built on React and Node.js — JavaScript is at the core.", "skills_needed": ["JavaScript", "Node.js", "React", "SQL"]},
        {"company": "Airbnb", "role": "UI Engineer", "industry": "Travel & Hospitality", "match_score": 83, "reason": "Airbnb invented React Native and has a strong JavaScript engineering culture.", "skills_needed": ["JavaScript", "React", "CSS", "A11y"]},
    ],
    "react": [
        {"company": "Vercel", "role": "Frontend Developer", "industry": "Developer Tools", "match_score": 94, "reason": "Vercel is the company behind Next.js. React expertise is the most valued skill here.", "skills_needed": ["React", "Next.js", "TypeScript", "CSS"]},
        {"company": "Notion", "role": "Product Engineer", "industry": "Productivity Software", "match_score": 89, "reason": "Notion's web product is a rich React application that requires deep component architecture knowledge.", "skills_needed": ["React", "TypeScript", "WebSockets", "Performance"]},
    ],
    "machine learning": [
        {"company": "OpenAI", "role": "ML Engineer", "industry": "Artificial Intelligence", "match_score": 96, "reason": "OpenAI is at the frontier of ML research and engineering. Your ML skills are highly relevant.", "skills_needed": ["Python", "PyTorch", "LLMs", "CUDA"]},
        {"company": "DeepMind", "role": "Research Engineer", "industry": "AI Research", "match_score": 93, "reason": "DeepMind focuses on cutting-edge ML research with a strong emphasis on reinforcement learning.", "skills_needed": ["Python", "TensorFlow", "Mathematics", "Research"]},
        {"company": "Hugging Face", "role": "ML Platform Engineer", "industry": "AI Tools", "match_score": 90, "reason": "Hugging Face builds the leading open-source ML tooling ecosystem — a natural fit for ML engineers.", "skills_needed": ["Python", "PyTorch", "Transformers", "Docker"]},
    ],
    "sql": [
        {"company": "Snowflake", "role": "Data Engineer", "industry": "Cloud Data Warehousing", "match_score": 91, "reason": "Snowflake is a leader in cloud data platforms and SQL is the primary querying language.", "skills_needed": ["SQL", "Python", "dbt", "Cloud"]},
        {"company": "Databricks", "role": "Analytics Engineer", "industry": "Data & AI", "match_score": 88, "reason": "Databricks integrates Spark and SQL for large-scale data processing — SQL expertise is essential.", "skills_needed": ["SQL", "PySpark", "Delta Lake", "Python"]},
    ],
    "default": [
        {"company": "Amazon", "role": "Software Development Engineer", "industry": "Cloud & E-Commerce", "match_score": 78, "reason": "Amazon hires across all engineering specializations and offers broad opportunities.", "skills_needed": ["Data Structures", "Algorithms", "System Design", "AWS"]},
        {"company": "Microsoft", "role": "Software Engineer", "industry": "Cloud & Productivity", "match_score": 75, "reason": "Microsoft has roles across Azure, Office, and Xbox — diverse opportunities.", "skills_needed": ["C#", "Cloud", "APIs", "Testing"]},
        {"company": "Infosys", "role": "Systems Engineer", "industry": "IT Services", "match_score": 72, "reason": "Infosys is a leading IT firm that offers strong career growth paths for freshers and experienced engineers.", "skills_needed": ["Any Language", "SQL", "Communication", "Agile"]},
        {"company": "TCS", "role": "Associate Engineer", "industry": "IT Consulting", "match_score": 70, "reason": "Tata Consultancy Services is one of the largest employers of tech talent globally.", "skills_needed": ["Java/Python", "SQL", "Problem Solving", "Git"]},
    ]
}

def get_career_recommendations(experience: str, skills: list, education: str, interests: str = "") -> dict:
    """
    Returns AI-powered career recommendations: companies, roles, match scores, and reasons.
    Uses OpenAI if available, otherwise falls back to a curated static dataset.
    """
    skills_str = ", ".join(skills) if skills else "general programming"
    client = get_openai_client()

    if client:
        prompt = f"""
        You are a senior career counsellor helping a tech professional find their ideal job.

        Candidate Profile:
        - Experience: {experience}
        - Known Skills: {skills_str}
        - Education: {education}
        - Interests / Preferred Industries: {interests or 'Open to any'}

        Based on this profile, recommend exactly 6 real-world companies and specific job roles that are the best fit.

        For each recommendation provide:
        - company: the real company name
        - role: the specific job title
        - industry: the company's industry sector
        - match_score: a numeric score 0-100 representing how well the candidate fits
        - reason: a 1-2 sentence explanation of why this is a great match
        - skills_needed: a list of 3-4 skills to focus on for this role

        Also provide a brief overall summary (2-3 sentences) about the candidate's career trajectory.

        Format STRICTLY as JSON:
        {{
            "summary": "Brief overall career summary here...",
            "recommendations": [
                {{
                    "company": "Company Name",
                    "role": "Job Title",
                    "industry": "Industry Sector",
                    "match_score": 88,
                    "reason": "Why this matches the candidate...",
                    "skills_needed": ["Skill1", "Skill2", "Skill3"]
                }}
            ]
        }}

        Only return valid JSON. No markdown, no extra text.
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a career counsellor. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"OpenAI career recommendation failed, using fallback: {e}")

    # Fallback: match skills against our local database
    recommendations = []
    seen_companies = set()
    skills_lower = [s.lower() for s in skills]

    for skill in skills_lower:
        if skill in CAREER_FALLBACK_DB:
            for rec in CAREER_FALLBACK_DB[skill]:
                if rec["company"] not in seen_companies:
                    seen_companies.add(rec["company"])
                    recommendations.append(rec)

    # If not enough matches, add defaults
    if len(recommendations) < 4:
        for rec in CAREER_FALLBACK_DB["default"]:
            if rec["company"] not in seen_companies and len(recommendations) < 6:
                seen_companies.add(rec["company"])
                recommendations.append(rec)

    # Sort by match_score descending and take top 6
    recommendations = sorted(recommendations, key=lambda x: x["match_score"], reverse=True)[:6]

    summary = f"Based on your {experience} experience with {skills_str}, you are well-positioned for roles in software engineering and data-driven fields. Focus on deepening your expertise in your primary skills while broadening your knowledge of cloud platforms and system design to accelerate your career growth."

    return {
        "summary": summary,
        "recommendations": recommendations
    }

