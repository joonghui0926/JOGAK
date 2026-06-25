from uuid import uuid4
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from jogak_api.core.config import get_settings
from jogak_api.core.security import create_access_token
from jogak_api.db.models import Account, User
from jogak_api.db.session import get_db
from jogak_api.schemas import AuthToken, EmailStartRequest

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


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
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID is not configured yet")
        redirect_uri = settings.google_redirect_uri or "http://localhost:8000/auth/oauth/google/callback"
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "online",
            "include_granted_scopes": "true",
            "state": uuid4().hex,
        }
        return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
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


@router.get("/oauth/{provider}/callback", response_model=None)
def oauth_callback(provider: str, code: str | None = None, db: Session = Depends(get_db)) -> AuthToken | RedirectResponse:
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")
    if provider == "google":
        return _google_oauth_callback(code, db)
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


def _google_oauth_callback(code: str, db: Session) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth credentials are not configured")

    redirect_uri = settings.google_redirect_uri or "http://localhost:8000/auth/oauth/google/callback"
    try:
        with httpx.Client(timeout=15.0) as client:
            token_response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not access_token:
                raise HTTPException(status_code=502, detail="Google OAuth token response did not include access_token")

            userinfo_response = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            profile = userinfo_response.json()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google OAuth request failed") from exc

    google_sub = str(profile.get("sub") or "")
    if not google_sub:
        raise HTTPException(status_code=502, detail="Google profile did not include a stable user id")

    email = profile.get("email")
    email_verified = bool(profile.get("email_verified"))
    display_name = profile.get("name") or (email.split("@")[0] if isinstance(email, str) else "Google 사용자")
    provider_account_id = google_sub

    account = (
        db.query(Account)
        .filter(Account.provider == "google", Account.provider_account_id == provider_account_id)
        .one_or_none()
    )
    if account:
        user = db.get(User, account.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if email_verified and email and not user.email:
            user.email = email
        user.display_name = display_name or user.display_name
        user.is_guest = False
    else:
        user = db.query(User).filter(User.email == email).one_or_none() if email_verified and email else None
        if user is None:
            user = User(
                email=email if email_verified else None,
                display_name=display_name,
                is_guest=False,
            )
            db.add(user)
            db.flush()
        else:
            user.display_name = display_name or user.display_name
            user.is_guest = False
        db.add(Account(user_id=user.id, provider="google", provider_account_id=provider_account_id))

    db.commit()
    db.refresh(user)

    jogak_token = create_access_token(user.id, is_guest=False)
    frontend_url = settings.frontend_app_url.rstrip("/")
    fragment = urlencode(
        {
            "auth_token": jogak_token,
            "auth_provider": "google",
            "user_name": user.display_name,
        }
    )
    return RedirectResponse(f"{frontend_url}/#{fragment}")
