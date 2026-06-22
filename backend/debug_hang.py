import sys
import os
import faulthandler
faulthandler.enable()

print("1. Patching BSON...")
try:
    import bson
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson
        sys.modules["bson"] = pymongo_bson
        from bson import ObjectId
        print("BSON patched")
    except Exception as e:
        print("BSON patch failed:", e)

print("2. Importing fastapi...")
from fastapi import FastAPI
print("FastAPI imported")

print("3. Importing database config...")
from src.config.database import init_database
print("Database config imported")

print("4. Importing database_service...")
from src.config.database_service import research_db
print("database_service imported")

print("5. Importing tools...")
from src.config.tools import SELECTED_RAG_PROVIDER
print("tools imported")

print("6. Importing vli config...")
from src.config.vli import VAULT_ROOT, get_action_plan_path
print("vli config imported")

print("7. Importing graph builder...")
from src.graph.builder import build_graph_with_memory
print("graph builder imported")

print("8. Importing chat_stream_message...")
from src.graph.checkpoint import chat_stream_message
print("chat_stream_message imported")

print("9. Importing NativeMongoDBSaver...")
from src.graph.mongodb_checkpointer import NativeMongoDBSaver
print("NativeMongoDBSaver imported")

print("10. Importing LLM models...")
from src.llms.llm import get_configured_llm_models
print("LLM models imported")

print("11. Importing RAG retriever...")
from src.rag.builder import build_retriever
print("RAG retriever imported")

print("12. Importing milvus...")
from src.rag.milvus import load_examples
print("milvus imported")

print("13. Importing full src.server.app...")
from src.server.app import app
print("src.server.app imported successfully!")
