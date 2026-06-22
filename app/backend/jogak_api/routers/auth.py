from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from jogak_api.core.config import get_settings
from jogak_api.core.security import create_access_token
from jogak_api.db.models import Account, User
from jogak_api.db.session import get_db
from jogak_api.schemas import AuthToken, EmailStartRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/guest", response_model=AuthToken)
def guest_login(db: Session = Depends(get_db)) -> AuthToken:
    user = User(display_name=f"게스트-{uuid4().hex[:6]}", is_guest=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthToken(access_token=create_access_token(user.id, is_guest=True), user=user)


@router.post("/email/start")
def email_start(payload: EmailStartRequest, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.email == str(payload.email)).one_or_none()
    if user is None:
        user = User(email=str(payload.email), display_name=payload.email.split("@")[0], is_guest=False)
        db.add(user)
        db.commit()
    return {
        "ok": True,
        "message": "이메일 인증코드 발송 큐가 준비됐습니다. SMTP 설정 후 실제 발송됩니다.",
    }


@router.get("/oauth/{provider}")
def oauth_start(provider: str) -> RedirectResponse:
    settings = get_settings()
    if provider == "google":
        if not settings.google_client_id:
            raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured yet")
        raise HTTPException(status_code=501, detail="Google OAuth callback wiring is ready for credentials")
    if provider == "kakao":
        if not settings.kakao_client_id:
            raise HTTPException(status_code=503, detail="KAKAO_CLIENT_ID is not configured yet")
        redirect_uri = settings.kakao_redirect_uri or "http://localhost:8000/auth/oauth/kakao/callback"
        kakao_url = (
            "https://kauth.kakao.com/oauth/authorize"
            f"?response_type=code&client_id={settings.kakao_client_id}&redirect_uri={redirect_uri}"
        )
        return RedirectResponse(kakao_url)
    raise HTTPException(status_code=404, detail="Unsupported OAuth provider")


@router.get("/oauth/{provider}/callback")
def oauth_callback(provider: str, code: str | None = None, db: Session = Depends(get_db)) -> AuthToken:
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")
    provider_account_id = f"{provider}:{code[:12]}"
    account = (
        db.query(Account)
        .filter(Account.provider == provider, Account.provider_account_id == provider_account_id)
        .one_or_none()
    )
    if account:
        user = db.get(User, account.user_id)
    else:
        user = User(display_name=f"{provider} 사용자", is_guest=False)
        db.add(user)
        db.flush()
        db.add(Account(user_id=user.id, provider=provider, provider_account_id=provider_account_id))
        db.commit()
        db.refresh(user)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return AuthToken(access_token=create_access_token(user.id, is_guest=False), user=user)
