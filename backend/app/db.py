# This file is the database connection setup for your backend
# Its job is to connect FastAPI to PostgreSQL safely and 
# give each API request its own database session

import os
from dotenv import load_dotenv

load_dotenv()
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5433/postgres")

# Clean up accidental prefixes if the user pasted key name in value field
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL.replace("DATABASE_URL=", "", 1)
elif DATABASE_URL.startswith("DATABASE_URL"):
    DATABASE_URL = DATABASE_URL.replace("DATABASE_URL", "", 1)

# Render provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine. Connect args are not needed for postgres, but we can set pool size
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session in FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
