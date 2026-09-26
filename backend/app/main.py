from contextlib import asynccontextmanager
import json
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from io import BytesIO

from .auth import complete_onboarding, current_user, google_login_user, init_auth_database, login_user, mark_welcome_seen, register_user, revoke_token
from .ai import OrvixAI
from .config import get_settings
from .conversations import append_exchange, get_conversation, list_conversations
from .documents import delete_document, list_documents, save_document
from .schemas import (
    AdminLoginRequest,
    AuthRequest,
    GoogleAuthRequest,
    AuthResponse,
    CheckoutRequest,
    CheckoutResponse,
    ChatRequest,
    ChatResponse,
    CoreProcessRequest,
    CoreProcessResponse,
    ConversationDetail,
    ConversationsResponse,
    DocumentsResponse,
    ExamModeRequest,
    ExamModeResponse,
    OnboardingRequest,
    QuizRequest,
    QuizExportRequest,
    QuizResponse,
    TextResponse,
    TopicRequest,
    UserProfile,
    WaitlistRequest,
    MAX_CONTEXT_MESSAGES,
)
from .quiz_word import build_quiz_docx
from .subscriptions import credit_cost, ensure_ai_quota, ensure_document_quota, join_waitlist, plans_config, record_ai_request, subscription_status
from .payments import create_checkout, apply_geniuspay_webhook, valid_geniuspay_signature
from .core_engine import OrvixCoreEngine
from .model_gateway import ModelGateway, create_model_provider
from .memory import remember, relevant
from .admin import admin_login, dashboard, require_superadmin

settings = get_settings()
logger = logging.getLogger("orvix.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_auth_database()
    app.state.ai = OrvixAI()
    yield


def get_ai() -> OrvixAI:
    if not hasattr(app.state, "ai"):
        app.state.ai = OrvixAI()
    return app.state.ai


core_engine = OrvixCoreEngine(ModelGateway(create_model_provider()))


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Orvix-Language", "X-Request-ID"],
)

@app.post(f"{settings.api_prefix}/admin/login")
async def superadmin_login(payload: AdminLoginRequest):
    return {"token": admin_login(payload.phone, payload.password)}

@app.get(f"{settings.api_prefix}/admin/dashboard")
async def superadmin_dashboard(_: str = Depends(require_superadmin)):
    return dashboard()


@app.post("/core/process")
async def process_core(payload: CoreProcessRequest, user: UserProfile = Depends(current_user)):
    """Provider-independent native core entry point for future clients."""
    try:
        return await core_engine.generate(user_id=user.id, session_id=payload.session_id, message=payload.message, language=payload.language)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    logger.info("request_complete request_id=%s method=%s path=%s status=%s duration_ms=%.1f", request_id, request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.get("/health")
async def health():
    provider_healthy = await core_engine.gateway.provider.health_check()
    return {
        "status": "ok" if provider_healthy else "degraded",
        "service": "orvix-api",
        "provider": settings.model_provider,
        "model": settings.gemini_model if settings.model_provider.lower() == "gemini" else settings.ollama_model,
        "ai": "healthy" if provider_healthy else "unhealthy",
        "storage": "postgresql" if settings.database_url else "filesystem",
    }


@app.get("/ready")
async def ready():
    provider_healthy = await core_engine.gateway.provider.health_check()
    return {
        "status": "ready" if provider_healthy else "not_ready",
        "provider": settings.model_provider,
        "model": settings.gemini_model if settings.model_provider.lower() == "gemini" else settings.ollama_model,
        "ai": provider_healthy,
    }


@app.get("/")
async def root():
    return {
        "service": "orvix-api",
        "status": "ok",
        "docs": "/docs",
        "api": settings.api_prefix,
    }


@app.get(f"{settings.api_prefix}/status")
async def status(user: UserProfile = Depends(current_user)):
    return {
        "service": "orvix-api",
        "status": "ok",
        "model": settings.ollama_model,
        "documents": len(list_documents(user.id)),
        "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
        "user": user,
    }


@app.post(f"{settings.api_prefix}/auth/register", response_model=AuthResponse)
async def register(payload: AuthRequest):
    token, user = register_user(payload.phone, payload.password)
    return AuthResponse(token=token, user=user)


@app.post(f"{settings.api_prefix}/auth/login", response_model=AuthResponse)
async def login(payload: AuthRequest):
    token, user = login_user(payload.phone, payload.password)
    return AuthResponse(token=token, user=user)

@app.post(f"{settings.api_prefix}/auth/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest):
    token, user, existing_account = google_login_user(payload.credential)
    return AuthResponse(token=token, user=user, existing_account=existing_account)


@app.get(f"{settings.api_prefix}/auth/me", response_model=UserProfile)
async def me(user: UserProfile = Depends(current_user)):
    return user


@app.post(f"{settings.api_prefix}/auth/onboarding", response_model=UserProfile)
async def onboarding(payload: OnboardingRequest, user: UserProfile = Depends(current_user)):
    return complete_onboarding(user.id, payload)


@app.post(f"{settings.api_prefix}/auth/welcome-seen", response_model=UserProfile)
async def welcome_seen(user: UserProfile = Depends(current_user)):
    return mark_welcome_seen(user.id)


@app.post(f"{settings.api_prefix}/auth/logout")
async def logout(authorization: str | None = Header(default=None), user: UserProfile = Depends(current_user)):
    revoke_token(authorization.removeprefix("Bearer ").strip() if authorization else "")
    return {"status": "ok"}


@app.post(f"{settings.api_prefix}/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, language: str = Header("Français", alias="X-Orvix-Language"), user: UserProfile = Depends(current_user)):
    action = "chat_with_documents" if payload.document_ids else "chat"
    cost = credit_cost(action)
    ensure_ai_quota(user.id, cost)
    history = payload.history[-MAX_CONTEXT_MESSAGES:]
    if payload.conversation_id:
        history = get_conversation(user.id, payload.conversation_id).messages[-MAX_CONTEXT_MESSAGES:]
    language_instruction = {"English": "Respond in English.", "Italiano": "Rispondi in italiano.", "Español": "Responde en español."}.get(language, "Réponds en français.")
    remember(user.id, payload.message)
    answer = await get_ai().chat(
        f"{language_instruction}{relevant(user.id, payload.message)}\n\n{payload.message}",
        history,
        user,
        payload.document_ids,
    )
    record_ai_request(user.id, cost, action)
    conversation = append_exchange(user.id, payload.conversation_id, payload.message, answer, payload.document_ids)
    return ChatResponse(conversation_id=conversation.id, answer=answer)


@app.get(f"{settings.api_prefix}/conversations", response_model=ConversationsResponse)
async def conversations(user: UserProfile = Depends(current_user)):
    return ConversationsResponse(conversations=list_conversations(user.id))


@app.get(f"{settings.api_prefix}/conversations/{{conversation_id}}", response_model=ConversationDetail)
async def conversation(conversation_id: str, user: UserProfile = Depends(current_user)):
    return get_conversation(user.id, conversation_id)


@app.post(f"{settings.api_prefix}/revision", response_model=TextResponse)
async def revision(payload: TopicRequest, user: UserProfile = Depends(current_user)):
    cost = credit_cost("revision")
    ensure_ai_quota(user.id, cost)
    content = await get_ai().revision(payload.topic, user, payload.document_ids)
    record_ai_request(user.id, cost, "revision")
    return TextResponse(content=content)


@app.post(f"{settings.api_prefix}/quiz", response_model=QuizResponse)
async def quiz(payload: QuizRequest, user: UserProfile = Depends(current_user)):
    action = "quiz_short" if payload.count <= 5 else "quiz_long"
    cost = credit_cost(action)
    ensure_ai_quota(user.id, cost)
    result = await get_ai().quiz(payload.topic, payload.count, payload.quiz_type, user, payload.document_ids)
    record_ai_request(user.id, cost, action)
    return result


@app.post(f"{settings.api_prefix}/exam-mode", response_model=ExamModeResponse)
async def exam_mode(payload: ExamModeRequest, user: UserProfile = Depends(current_user)):
    cost = credit_cost("exam_plan")
    ensure_ai_quota(user.id, cost)
    result = await get_ai().exam_mode(payload.exam_date, payload.minutes_per_day, payload.confidence, payload.subject, user, payload.document_ids)
    record_ai_request(user.id, cost, "exam_plan")
    return result


@app.get(f"{settings.api_prefix}/subscription/plans")
async def subscription_plans():
    return plans_config()


@app.get(f"{settings.api_prefix}/subscription")
async def my_subscription(user: UserProfile = Depends(current_user)):
    return subscription_status(user.id)


@app.post(f"{settings.api_prefix}/subscription/waitlist")
async def subscription_waitlist(payload: WaitlistRequest, user: UserProfile = Depends(current_user)):
    return join_waitlist(user.id, payload.plan_id)


@app.post(f"{settings.api_prefix}/subscription/checkout", response_model=CheckoutResponse)
async def subscription_checkout(payload: CheckoutRequest, user: UserProfile = Depends(current_user)):
    return await create_checkout(user, payload.plan_id, payload.billing_cycle)


@app.get(f"{settings.api_prefix}/payments/geniuspay/webhook")
async def geniuspay_webhook_ping():
    return {"status": "ok"}


@app.post(f"{settings.api_prefix}/payments/geniuspay/webhook")
async def geniuspay_webhook(request: Request):
    raw_body = await request.body()
    if not valid_geniuspay_signature(raw_body, request.headers.get("X-Webhook-Signature"), request.headers.get("X-Webhook-Timestamp")):
        raise HTTPException(401, "Notification de paiement invalide.")
    payload = json.loads(raw_body)
    await apply_geniuspay_webhook(payload)
    return {"status": "ok"}


@app.post(f"{settings.api_prefix}/quiz/export")
async def export_quiz(payload: QuizExportRequest, user: UserProfile = Depends(current_user)):
    content = build_quiz_docx(payload)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="quiz-orvix.docx"'},
    )


@app.get(f"{settings.api_prefix}/documents", response_model=DocumentsResponse)
async def documents(user: UserProfile = Depends(current_user)):
    return DocumentsResponse(documents=list_documents(user.id))


@app.post(f"{settings.api_prefix}/documents", response_model=DocumentsResponse)
async def upload_documents(files: list[UploadFile] = File(...), user: UserProfile = Depends(current_user)):
    ensure_document_quota(user.id, len(list_documents(user.id)), len(files))
    for upload in files:
        await save_document(user.id, upload)
    return DocumentsResponse(documents=list_documents(user.id))


@app.delete(f"{settings.api_prefix}/documents/{{document_id}}", response_model=DocumentsResponse)
async def remove_document(document_id: str, user: UserProfile = Depends(current_user)):
    delete_document(user.id, document_id)
    return DocumentsResponse(documents=list_documents(user.id))
