from fastmcp import FastMCP
from research_agent.agent import ResearchAgent
import logging

# Ensure logging matches standard format
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP("NIM-Research-Agent")

@mcp.tool()
def run_research(query: str, instructions: str = "", timeout_minutes: int = 5) -> str:
    """
    Perform deep web research on a given topic using an autonomous web-searching and web-crawling subagent.
    Use this tool when you need current information, in-depth reports, or detailed analysis.
    The tool returns a beautifully structured, comprehensive Markdown report with citations.

    Args:
        query: The main topic, question, or research focus.
        instructions: Optional additional instructions, specific points to cover, or formatting wishes.
        timeout_minutes: Maximum time in minutes to let the agent run (default: 5). Increase for complex topics.
    """
    logger.info(f"MCP Tool 'run_research' invoked with query: '{query}' (timeout: {timeout_minutes}m)")
    try:
        agent = ResearchAgent(timeout_seconds=timeout_minutes * 60)
        report = agent.run(query, instructions)
        return report
    except FileNotFoundError as e:
        logger.error(f"Setup error: {e}")
        return f"Error: {e}\n\nPlease ensure the pi coding agent is installed: `npm install @earendil-works/pi-coding-agent`"
    except Exception as e:
        logger.error(f"Error executing run_research in MCP Server: {e}")
        return f"Error: Failed to perform research. Details: {e}"

def main():
    logger.info("Starting NIM-Research-Agent FastMCP Server...")
    mcp.run()

if __name__ == "__main__":
    main()
