# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from src.config.database_service import research_db

router = APIRouter()

# Pydantic models for API responses
class ResearchProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    tags: Optional[str]
    created_at: str
    updated_at: str

class ResearchSessionResponse(BaseModel):
    id: int
    project_id: int
    session_id: str
    title: Optional[str]
    status: str
    created_at: str
    updated_at: str
    message_count: int

class SessionMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    message_type: str
    tool_calls: Optional[str]
    created_at: str

class ResearchFindingResponse(BaseModel):
    id: int
    project_id: int
    title: str
    content: str
    category: str
    confidence: float
    source_documents: Optional[str]
    tags: Optional[str]
    created_at: str
    updated_at: str

class ResearchDocumentResponse(BaseModel):
    id: int
    project_id: int
    title: str
    content: Optional[str]
    source_url: Optional[str]
    document_type: str
    created_at: str

# API Endpoints
@router.get("/projects", response_model=List[ResearchProjectResponse])
async def get_research_projects():
    """Get all research projects."""
    try:
        projects = research_db.get_all_research_projects()
        return [
            ResearchProjectResponse(
                id=p.id,
                title=p.title,
                description=p.description,
                status=p.status,
                tags=p.tags,
                created_at=p.created_at.isoformat(),
                updated_at=p.updated_at.isoformat()
            ) for p in projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")

@router.get("/projects/{project_id}", response_model=ResearchProjectResponse)
async def get_research_project(project_id: int):
    """Get a specific research project."""
    try:
        project = research_db.get_research_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ResearchProjectResponse(
            id=project.id,
            title=project.title,
            description=project.description,
            status=project.status,
            tags=project.tags,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch project: {str(e)}")

@router.get("/projects/{project_id}/sessions", response_model=List[ResearchSessionResponse])
async def get_project_sessions(project_id: int):
    """Get all sessions for a research project."""
    try:
        sessions = research_db.get_research_sessions(project_id)
        return [
            ResearchSessionResponse(
                id=s.id,
                project_id=s.project_id,
                session_id=s.session_id,
                title=s.title,
                status=s.status,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
                message_count=len(research_db.get_session_messages(s.id))
            ) for s in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sessions: {str(e)}")

@router.get("/sessions/{session_id}/messages", response_model=List[SessionMessageResponse])
async def get_session_messages(session_id: int):
    """Get all messages for a research session."""
    try:
        messages = research_db.get_session_messages(session_id)
        return [
            SessionMessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                message_type=m.message_type,
                tool_calls=m.tool_calls,
                created_at=m.created_at.isoformat()
            ) for m in messages
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages: {str(e)}")

@router.get("/projects/{project_id}/findings", response_model=List[ResearchFindingResponse])
async def get_project_findings(project_id: int):
    """Get all findings for a research project."""
    try:
        findings = research_db.get_research_findings(project_id)
        return [
            ResearchFindingResponse(
                id=f.id,
                project_id=f.project_id,
                title=f.title,
                content=f.content,
                category=f.category,
                confidence=f.confidence,
                source_documents=f.source_documents,
                tags=f.tags,
                created_at=f.created_at.isoformat(),
                updated_at=f.updated_at.isoformat()
            ) for f in findings
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch findings: {str(e)}")

@router.get("/projects/{project_id}/documents", response_model=List[ResearchDocumentResponse])
async def get_project_documents(project_id: int):
    """Get all documents for a research project."""
    try:
        documents = research_db.get_research_documents(project_id)
        return [
            ResearchDocumentResponse(
                id=d.id,
                project_id=d.project_id,
                title=d.title,
                content=d.content,
                source_url=d.source_url,
                document_type=d.document_type,
                created_at=d.created_at.isoformat()
            ) for d in documents
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")

@router.post("/projects")
async def create_research_project(title: str, description: str = "", tags: str = ""):
    """Create a new research project."""
    try:
        project = research_db.create_research_project(title, description, tags)
        return {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "tags": project.tags,
            "created_at": project.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.post("/findings")
async def create_research_finding(
    project_id: int,
    title: str,
    content: str,
    category: str = "insight",
    confidence: float = 0.0,
    source_documents: str = "",
    tags: str = ""
):
    """Create a research finding."""
    try:
        finding = research_db.create_research_finding(
            project_id, title, content, category, confidence, source_documents, tags
        )
        return {
            "id": finding.id,
            "title": finding.title,
            "content": finding.content,
            "category": finding.category,
            "confidence": finding.confidence,
            "created_at": finding.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create finding: {str(e)}")

@router.post("/documents")
async def create_research_document(
    project_id: int,
    title: str,
    content: str = "",
    source_url: str = "",
    document_type: str = "web"
):
    """Create a research document."""
    try:
        document = research_db.create_research_document(
            project_id, title, content, source_url, document_type
        )
        return {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "source_url": document.source_url,
            "document_type": document.document_type,
            "created_at": document.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")
