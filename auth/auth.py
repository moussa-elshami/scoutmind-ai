import bcrypt
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session
from database.models import User, init_db, SessionLocal
from datetime import datetime
import os

# ─── District / Group / Unit Data ────────────────────────────────────────────
DISTRICTS = {
    "Beirut":   ["Beirut 1", "Beirut 2", "Beirut 3", "Beirut 4", "Beirut 7"],
    "South":    ["Saida 1", "Saida 4", "Saida 5", "Saida 6", "Hasbaya 1"],
    "Mountain": ["Brummana 1", "Rabieh 1", "Aley 1", "Monsef 1"],
    "Bekaa":    ["Zahle 1", "Zahle 2", "Zahle 3", "Zahle 4", "Zahle 5"],
}

UNITS = [
    "Beavers",
    "Cubs",
    "Girl Scouts",
    "Boy Scouts",
    "Pioneers",
    "Rovers",
]


# ─── Password Utilities ───────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ─── Email Verification ───────────────────────────────────────────────────────
def send_verification_email(to_email: str, full_name: str, token: str) -> bool:
    """
    Sends an email verification link via SMTP.
    Requires SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS in environment.
    Returns True on success, False on failure.
    """
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    app_url   = os.getenv("APP_URL", "http://localhost:8501")

    if not all([smtp_host, smtp_user, smtp_pass]):
        # SMTP not configured — skip verification in dev mode
        return False

    verify_link = f"{app_url}?verify_token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ScoutMind — Verify Your Email Address"
    msg["From"]    = smtp_user
    msg["To"]      = to_email

    text_body = f"""
Hello {full_name},

Welcome to ScoutMind. Please verify your email address by clicking the link below:

{verify_link}

If you did not create an account, please ignore this email.

The ScoutMind Team
Lebanese Scouts Association
"""

    html_body = f"""
<html>
  <body style="font-family: Georgia, serif; background: #f9f9f9; padding: 40px;">
    <div style="max-width: 520px; margin: auto; background: white;
                border: 1px solid #e0d6f5; border-radius: 8px; padding: 40px;">
      <h2 style="color: #6B21A8; margin-bottom: 8px;">ScoutMind</h2>
      <p style="color: #444; font-size: 15px;">Hello <strong>{full_name}</strong>,</p>
      <p style="color: #444; font-size: 15px;">
        Welcome to ScoutMind. Please verify your email address to activate your account.
      </p>
      <a href="{verify_link}"
         style="display: inline-block; margin: 24px 0; padding: 12px 28px;
                background: #6B21A8; color: white; text-decoration: none;
                border-radius: 6px; font-size: 15px;">
        Verify Email Address
      </a>
      <p style="color: #888; font-size: 13px;">
        If you did not create an account, please ignore this email.
      </p>
      <hr style="border: none; border-top: 1px solid #e0d6f5; margin: 24px 0;">
      <p style="color: #aaa; font-size: 12px;">
        ScoutMind &mdash; Lebanese Scouts Association
      </p>
    </div>
  </body>
</html>
"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[Email Error] {e}")
        return False


# ─── Auth Functions ───────────────────────────────────────────────────────────
def register_user(
    full_name: str,
    email: str,
    password: str,
    district: str,
    group_name: str,
    unit: str,
) -> dict:
    """
    Creates a new user account.
    Returns {"success": True, "email_sent": bool} or {"success": False, "error": str}
    """
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email.lower().strip()).first()
        if existing:
            return {"success": False, "error": "An account with this email already exists."}

        token         = secrets.token_urlsafe(32)
        password_hash = hash_password(password)

        user = User(
            full_name     = full_name.strip(),
            email         = email.lower().strip(),
            password_hash = password_hash,
            district      = district,
            group_name    = group_name,
            unit          = unit,
            is_verified   = False,
            verify_token  = token,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        email_sent = send_verification_email(email, full_name, token)

        # In dev mode (no SMTP configured), auto-verify the account
        if not email_sent:
            user.is_verified = True
            user.verify_token = None
            db.commit()

        return {"success": True, "email_sent": email_sent, "user_id": user.id}

    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def verify_email_token(token: str) -> dict:
    """Verifies an email token and activates the account."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.verify_token == token).first()
        if not user:
            return {"success": False, "error": "Invalid or expired verification link."}
        user.is_verified  = True
        user.verify_token = None
        db.commit()
        return {"success": True, "full_name": user.full_name}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def login_user(email: str, password: str) -> dict:
    """
    Authenticates a user.
    Returns {"success": True, "user": {...}} or {"success": False, "error": str}
    """
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        if not user:
            return {"success": False, "error": "No account found with this email."}
        if not verify_password(password, user.password_hash):
            return {"success": False, "error": "Incorrect password."}
        if not user.is_verified:
            return {"success": False, "error": "Please verify your email before logging in."}

        return {
            "success": True,
            "user": {
                "id":         user.id,
                "full_name":  user.full_name,
                "email":      user.email,
                "district":   user.district,
                "group_name": user.group_name,
                "unit":       user.unit,
            },
        }
    finally:
        db.close()

def update_profile(
    user_id: int,
    full_name: str,
    district: str,
    group_name: str,
    unit: str,
) -> dict:
    """Updates user profile. Email is not editable."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found."}

        user.full_name  = full_name.strip()
        user.district   = district
        user.group_name = group_name
        user.unit       = unit
        user.updated_at = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "user": {
                "id":         user.id,
                "full_name":  user.full_name,
                "email":      user.email,
                "district":   user.district,
                "group_name": user.group_name,
                "unit":       user.unit,
            },
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def get_user_by_id(user_id: int) -> dict | None:
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {
            "id":         user.id,
            "full_name":  user.full_name,
            "email":      user.email,
            "district":   user.district,
            "group_name": user.group_name,
            "unit":       user.unit,
        }
    finally:
        db.close()