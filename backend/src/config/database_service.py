from sqlalchemy.orm import Session
from .database import (
    ResearchProject, ResearchDocument, ResearchFinding,
    ResearchSession, SessionMessage, get_db
)
from typing import List, Optional
from datetime import datetime

class ResearchDatabaseService:
    """Service class for managing research data persistence."""

    @staticmethod
    def create_research_project(title: str, description: str = "", tags: str = "") -> ResearchProject:
        """Create a new research project."""
        with next(get_db()) as db:
            project = ResearchProject(
                title=title,
                description=description,
                tags=tags,
                status="active"
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            return project

    @staticmethod
    def get_research_project(project_id: int) -> Optional[ResearchProject]:
        """Get a research project by ID."""
        with next(get_db()) as db:
            return db.query(ResearchProject).filter(ResearchProject.id == project_id).first()

    @staticmethod
    def get_all_research_projects() -> List[ResearchProject]:
        """Get all research projects."""
        with next(get_db()) as db:
            return db.query(ResearchProject).order_by(ResearchProject.created_at.desc()).all()

    @staticmethod
    def create_research_session(project_id: int, session_id: str, title: str = "") -> ResearchSession:
        """Create a new research session."""
        with next(get_db()) as db:
            session = ResearchSession(
                project_id=project_id,
                session_id=session_id,
                title=title,
                status="active"
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    @staticmethod
    def save_session_message(session_id: int, role: str, content: str,
                           message_type: str = "text", tool_calls: str = "") -> SessionMessage:
        """Save a message to a research session."""
        with next(get_db()) as db:
            message = SessionMessage(
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                tool_calls=tool_calls
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            return message

    @staticmethod
    def create_research_finding(project_id: int, title: str, content: str,
                              category: str = "insight", confidence: float = 0.0,
                              source_documents: str = "", tags: str = "") -> ResearchFinding:
        """Create a research finding."""
        with next(get_db()) as db:
            finding = ResearchFinding(
                project_id=project_id,
                title=title,
                content=content,
                category=category,
                confidence=confidence,
                source_documents=source_documents,
                tags=tags
            )
            db.add(finding)
            db.commit()
            db.refresh(finding)
            return finding

    @staticmethod
    def create_research_document(project_id: int, title: str, content: str = "",
                               source_url: str = "", document_type: str = "web") -> ResearchDocument:
        """Create a research document."""
        with next(get_db()) as db:
            document = ResearchDocument(
                project_id=project_id,
                title=title,
                content=content,
                source_url=source_url,
                document_type=document_type
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            return document

    @staticmethod
    def get_research_sessions(project_id: int) -> List[ResearchSession]:
        """Get all sessions for a research project."""
        with next(get_db()) as db:
            return db.query(ResearchSession).filter(
                ResearchSession.project_id == project_id
            ).order_by(ResearchSession.created_at.desc()).all()

    @staticmethod
    def get_session_messages(session_id: int) -> List[SessionMessage]:
        """Get all messages for a research session."""
        with next(get_db()) as db:
            return db.query(SessionMessage).filter(
                SessionMessage.session_id == session_id
            ).order_by(SessionMessage.created_at.asc()).all()

    @staticmethod
    def get_research_findings(project_id: int) -> List[ResearchFinding]:
        """Get all findings for a research project."""
        with next(get_db()) as db:
            return db.query(ResearchFinding).filter(
                ResearchFinding.project_id == project_id
            ).order_by(ResearchFinding.created_at.desc()).all()

    @staticmethod
    def get_research_documents(project_id: int) -> List[ResearchDocument]:
        """Get all documents for a research project."""
        with next(get_db()) as db:
            return db.query(ResearchDocument).filter(
                ResearchDocument.project_id == project_id
            ).order_by(ResearchDocument.created_at.desc()).all()

    @staticmethod
    def extract_and_save_findings(content: str, project_id: int, session_id: str = None):
        """Extract and save research findings from content."""
        try:
            # Simple extraction logic - look for key insights
            findings = []

            # Look for sentences that might contain findings
            sentences = content.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and any(keyword in sentence.lower() for keyword in
                    ['found that', 'discovered', 'research shows', 'study found', 'results indicate',
                     'conclusion', 'key finding', 'important', 'significant', 'evidence suggests']):
                    findings.append(sentence)

            # Save extracted findings
            for finding in findings[:3]:  # Limit to 3 findings per message
                research_db.create_research_finding(
                    project_id=project_id,
                    title=f"Research Finding from Session {session_id or 'Unknown'}",
                    content=finding,
                    category="insight",
                    confidence=0.7,
                    tags="auto-extracted"
                )

        except Exception as e:
            # Silently fail for finding extraction
            pass

# Global service instance
research_db = ResearchDatabaseService()
