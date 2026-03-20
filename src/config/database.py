# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool
import os
from datetime import datetime
from typing import Optional

Base = declarative_base()

class ResearchProject(Base):
    """Model for research projects."""
    __tablename__ = "research_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active")  # active, completed, archived
    tags = Column(String(1000))  # comma-separated tags

    # Relationships
    documents = relationship("ResearchDocument", back_populates="project", cascade="all, delete-orphan")
    findings = relationship("ResearchFinding", back_populates="project", cascade="all, delete-orphan")
    sessions = relationship("ResearchSession", back_populates="project", cascade="all, delete-orphan")

class ResearchDocument(Base):
    """Model for research documents."""
    __tablename__ = "research_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("research_projects.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    source_url = Column(String(2000))
    document_type = Column(String(100))  # pdf, web, article, etc.
    file_path = Column(String(1000))  # local file path if applicable
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    document_metadata = Column(Text)  # JSON string for additional metadata

    # Vector database reference
    vector_id = Column(String(500))  # ID in vector database (Milvus, etc.)

    # Relationships
    project = relationship("ResearchProject", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    """Model for document chunks (for RAG)."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("research_documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    embedding = Column(Text)  # Store embedding as JSON string if needed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("ResearchDocument", back_populates="chunks")

class ResearchFinding(Base):
    """Model for research findings and insights."""
    __tablename__ = "research_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("research_projects.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100))  # fact, insight, hypothesis, conclusion
    confidence = Column(Float)  # 0.0 to 1.0
    source_documents = Column(Text)  # JSON array of document IDs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tags = Column(String(1000))  # comma-separated tags

    # Relationships
    project = relationship("ResearchProject", back_populates="findings")

class ResearchSession(Base):
    """Model for research sessions/chat history."""
    __tablename__ = "research_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("research_projects.id"), nullable=False)
    session_id = Column(String(500), nullable=False)  # LangGraph thread ID
    title = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active")  # active, completed, archived

    # Relationships
    project = relationship("ResearchProject", back_populates="sessions")
    messages = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan")

class SessionMessage(Base):
    """Model for individual messages in research sessions."""
    __tablename__ = "session_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    message_type = Column(String(50))  # text, tool_call, tool_result
    tool_calls = Column(Text)  # JSON string for tool calls
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ResearchSession", back_populates="messages")

# Database connection and session management
def get_database_url() -> str:
    """Get database URL from environment variables."""
    # Check if full URL is provided
    full_url = os.getenv("RESEARCH_DB_URL")
    if full_url:
        return full_url

    # Otherwise construct from individual components
    host = os.getenv("RESEARCH_DB_HOST", "localhost")
    port = os.getenv("RESEARCH_DB_PORT", "5432")
    database = os.getenv("RESEARCH_DB_NAME", "deerflow_research")
    user = os.getenv("RESEARCH_DB_USER", "postgres")
    password = os.getenv("RESEARCH_DB_PASSWORD", "postgres")

    return f"postgresql+pg8000://{user}:{password}@{host}:{port}/{database}"

def get_database_engine():
    """Create and return database engine."""
    database_url = get_database_url()

    # Configure connection pool for PostgreSQL
    if database_url.startswith("postgresql"):
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False  # Set to True for SQL query logging
        )
    else:
        # For other databases, use default settings
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            echo=False
        )

    return engine

def get_session_local():
    """Get session local for database operations."""
    engine = get_database_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal

def create_tables():
    """Create all database tables."""
    engine = get_database_engine()
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency for FastAPI to get database session."""
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()

# Initialize database on import
def init_database():
    """Initialize database and create tables if they don't exist."""
    print("=== Starting Database Initialization ===")

    # Log environment detection
    railway_env = os.getenv("RAILWAY_ENVIRONMENT")
    railway_project = os.getenv("RAILWAY_PROJECT_ID")
    print(f"Railway Environment: {railway_env}")
    print(f"Railway Project ID: {railway_project}")

    try:
        # Log database URL construction
        db_url = get_database_url()
        print(f"Database URL: {db_url.replace(db_url.split('@')[0].split('//')[1], '***:***@') if '@' in db_url else db_url}")

        # Test database connection first
        print("Testing database connection...")
        engine = get_database_engine()
        print(f"Database engine created: {type(engine)}")

        with engine.connect() as conn:
            print("Executing connection test...")
            result = conn.execute(text("SELECT 1"))
            print(f"Connection test result: {result.fetchone()}")
        print("✅ Database connection successful")

        # Create tables
        print("Creating database tables...")
        create_tables()
        print("✅ Database tables created successfully")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        if "pg8000" in str(e).lower() or "postgresql" in str(e).lower():
            print("⚠️  PostgreSQL driver not available. Database features will be disabled.")
            print("💡 To enable database features, ensure pg8000 is installed.")
            print("   The requirements.txt should include: pg8000==1.31.2")
            print("   pg8000 is a pure Python driver that doesn't require compilation")
            return False
        else:
            print(f"❌ Unexpected import error: {e}")
            raise

    except Exception as e:
        print(f"❌ Database Error: {type(e).__name__}: {e}")

        # Log additional context for debugging
        print("🔍 Debug Information:")
        print(f"  - Python version: {__import__('sys').version}")
        print(f"  - Current working directory: {os.getcwd()}")

        # Check if we're in a Railway environment
        if railway_env or railway_project:
            print("🚂 Running on Railway - continuing without database initialization")
            print("💡 Railway Deployment Tips:")
            print("   1. Check Railway PostgreSQL service is properly attached")
            print("   2. Verify environment variables are set correctly")
            print("   3. Try redeploying with: railway up")
            print("   4. Check Railway logs for more detailed error information")
            return False
        else:
            print("💻 Local development - raising error for debugging")
            raise

    print("=== Database Initialization Complete ===")
    return True
