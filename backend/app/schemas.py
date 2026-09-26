from typing import Literal

from pydantic import BaseModel, Field

MAX_CONTEXT_MESSAGES = 60  # 30 échanges utilisateur/assistant au maximum


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class ChatRequest(BaseModel):
    conversation_id: str = ""
    message: str = Field(min_length=1, max_length=8_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=MAX_CONTEXT_MESSAGES)
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class TopicRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class QuizRequest(TopicRequest):
    count: int = Field(default=5, ge=1, le=200)
    quiz_type: Literal["multiple_choice", "traditional"] = "multiple_choice"


class QuizQuestion(BaseModel):
    question: str
    choices: list[str] = Field(default_factory=list, max_length=6)
    answer_index: int = Field(default=-1, ge=-1)
    expected_answer: str = ""
    explanation: str


class QuizResponse(BaseModel):
    title: str
    questions: list[QuizQuestion]


class ExamModeRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=20)
    exam_date: str = Field(min_length=10, max_length=10)
    minutes_per_day: int = Field(ge=10, le=360)
    confidence: int = Field(ge=1, le=5)
    subject: str = Field(default="", max_length=160)


class ExamDay(BaseModel):
    day: int
    title: str
    tasks: list[str]
    minutes: int


class ExamModeResponse(BaseModel):
    title: str
    readiness_score: int = Field(ge=0, le=100)
    summary: str
    mastered: list[str]
    priorities: list[str]
    plan: list[ExamDay]
    first_questions: list[QuizQuestion]


class QuizExportRequest(QuizResponse):
    quiz_type: Literal["multiple_choice", "traditional"] = "multiple_choice"


class TextResponse(BaseModel):
    content: str


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str


class CoreProcessRequest(BaseModel):
    session_id: str = Field(default="", max_length=120)
    message: str = Field(min_length=1, max_length=8_000)
    language: str = Field(default="Français", max_length=40)


class CoreProcessResponse(BaseModel):
    requestId: str
    status: str
    intent: str
    response: dict
    actions: list[dict]
    metadata: dict


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: str


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessage]
    document_ids: list[str] = Field(default_factory=list)


class ConversationsResponse(BaseModel):
    conversations: list[ConversationSummary]


class DocumentInfo(BaseModel):
    id: str
    number: int
    name: str
    size: int
    created_at: str


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]


class AuthRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=30)
    password: str = Field(min_length=6, max_length=120)

class AdminLoginRequest(BaseModel):
    phone: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=200)

class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=5000)


class UserProfile(BaseModel):
    id: str
    phone: str
    name: str = "Etudiant"
    onboarding_completed: bool = False
    level: str = ""
    subjects: list[str] = Field(default_factory=list)
    goal: str = ""
    learning_style: str = ""
    difficulties: str = ""
    welcome_seen: bool = False


class OnboardingRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    level: str = Field(min_length=2, max_length=80)
    subjects: list[str] = Field(default_factory=list, max_length=8)
    goal: str = Field(min_length=2, max_length=300)
    learning_style: str = Field(min_length=2, max_length=120)
    difficulties: str = Field(default="", max_length=500)


class AuthResponse(BaseModel):
    token: str
    user: UserProfile
    existing_account: bool = False


class CheckoutRequest(BaseModel):
    plan_id: Literal["student", "pro"]
    billing_cycle: Literal["monthly", "annual"]


class WaitlistRequest(BaseModel):
    plan_id: Literal["student", "pro"]


class CheckoutResponse(BaseModel):
    transaction_id: str
    payment_url: str
    simulation: bool = False
