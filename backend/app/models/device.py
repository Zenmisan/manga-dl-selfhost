from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(String, primary_key=True)           # UUID
    user_id = Column(String, nullable=False, index=True)  # Supabase user UUID
    device_fingerprint = Column(String, nullable=False)   # hash(user_agent + ip)
    device_name = Column(String, nullable=False)          # human-readable label
    last_active = Column(DateTime, server_default=func.now(), onupdate=func.now())
    locked_until = Column(DateTime, nullable=True)        # set when forfeited
    created_at = Column(DateTime, server_default=func.now())
