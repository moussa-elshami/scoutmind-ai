from sqlalchemy.orm import Session
from database.models import ChatSession, ChatMessage, SessionLocal
from datetime import datetime

def create_session(user_id: int, title: str, unit: str = None, theme: str = None, meeting_date: str = None) -> dict:
    db: Session = SessionLocal()
    try:
        session = ChatSession(
            user_id      = user_id,
            title        = title,
            unit         = unit,
            theme        = theme,
            meeting_date = meeting_date,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return {"success": True, "session_id": session.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def get_user_sessions(user_id: int) -> list:
    db: Session = SessionLocal()
    try:
        sessions = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )
        return [
            {
                "id":           s.id,
                "title":        s.title,
                "unit":         s.unit,
                "theme":        s.theme,
                "meeting_date": s.meeting_date,
                "updated_at":   s.updated_at.strftime("%d/%m/%Y %H:%M"),
            }
            for s in sessions
        ]
    finally:
        db.close()

def add_message(session_id: int, user_id: int, role: str, content: str) -> dict:
    db: Session = SessionLocal()
    try:
        msg = ChatMessage(
            session_id = session_id,
            user_id    = user_id,
            role       = role,
            content    = content,
        )
        db.add(msg)

        # Update session timestamp
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.updated_at = datetime.utcnow()

        db.commit()
        return {"success": True, "message_id": msg.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def get_session_messages(session_id: int, user_id: int) -> list:
    db: Session = SessionLocal()
    try:
        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == session_id,
                ChatMessage.user_id    == user_id,
            )
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [
            {
                "role":       m.role,
                "content":    m.content,
                "created_at": m.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for m in messages
        ]
    finally:
        db.close()

def update_session_title(session_id: int, user_id: int, title: str):
    db: Session = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.id      == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if session:
            session.title      = title
            session.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()

def delete_session(session_id: int, user_id: int) -> dict:
    db: Session = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.id      == session_id,
            ChatSession.user_id == user_id,
        ).first()
        if not session:
            return {"success": False, "error": "Session not found."}

        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.delete(session)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()