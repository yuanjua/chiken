import asyncio
from fastmcp import Client, FastMCP
from loguru import logger
# HTTP server
client = Client("http://localhost:8000/mcp")

async def main():
    async with client:
        # Basic server interaction
        await client.ping()
        
        # List available operations
        tools = await client.list_tools()
        for tool in tools:
            # structure output
            logger.info('-'*100)
            logger.info(f"tool: {tool.name}")
            logger.info(f"tool: {tool.description}")
            logger.info('-'*100)
        resources = await client.list_resources()
        logger.info("available resources: ", resources)
        prompts = await client.list_prompts()
        logger.info("available prompts: ", prompts)
        
        # Execute operations
        result = await client.call_tool("list_active_knowledge_bases_names", {})
        logger.info(result)

        result = await client.call_tool("search_documents", {"query": "What is the capital of France?"})
        logger.info("\n### Semantic query example ###")
        logger.info(result.data[0])

if __name__ == "__main__":
    asyncio.run(main())