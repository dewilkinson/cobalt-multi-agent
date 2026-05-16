import asyncio
from fastapi import FastAPI
from src.server.app import app

async def test_lifespan():
    async with app.router.lifespan_context(app):
        pass

if __name__ == "__main__":
    asyncio.run(test_lifespan())
