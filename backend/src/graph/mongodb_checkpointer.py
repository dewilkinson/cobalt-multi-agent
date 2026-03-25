import asyncio
import logging
from typing import (
    Any,
    Iterator,
    Optional,
)

from langchain_core.runnables import RunnableConfig, run_in_executor
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class NativeMongoDBSaver(BaseCheckpointSaver):
    """A clean, native MongoDB checkpointer that avoids the 'bson' version conflict.
    Uses the project's verified pymongo installation directly.
    """
    def __init__(
        self,
        client: MongoClient,
        db_name: str = "checkpointing_db",
        checkpoint_collection_name: str = "checkpoints",
        serde: SerializerProtocol | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db[checkpoint_collection_name]
        self.serde = serde or JsonPlusSerializer()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        if checkpoint_id:
            query = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id}
        else:
            query = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}

        doc = self.collection.find_one(query, sort=[("checkpoint_id", -1)])
        if not doc:
            return None

        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": doc["checkpoint_id"]}},
            checkpoint=self.serde.loads_typed((doc["type"], doc["checkpoint"])),
            metadata=doc.get("metadata", {}),
            parent_config=doc.get("parent_config"),
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"]["checkpoint_ns"]
            checkpoint_id = checkpoint["id"]
            type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)

            doc = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "type": type_,
                "checkpoint": serialized_checkpoint,
                "metadata": metadata,
                "parent_config": config.get("parent_config"),
            }

            self.collection.update_one(
                {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
                {"$set": doc},
                upsert=True,
            )

            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            }
        except Exception as e:
            logger.exception(f"CRITICAL ERROR in NativeMongoDBSaver.put: {e}")
            raise

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await run_in_executor(None, self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await run_in_executor(None, self.put, config, checkpoint, metadata, new_versions)

    async def alist(self, *args, **kwargs) -> Any:
        # Minimal list implementation to satisfy interface
        if False:
            yield None

    @classmethod
    def from_conn_string(cls, conn_string: str, **kwargs: Any) -> "NativeMongoDBSaver":
        client = MongoClient(conn_string)
        return cls(client, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
