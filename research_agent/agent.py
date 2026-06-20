import os
import sys
import shutil
import json
import uuid
import logging
import subprocess
import signal
from typing import Optional
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# We define the code of search_tool.py dynamically so we can dump it into the run session folder.
# This CLI tool is passed to the pi agent, so it can run search and scraping directly using python.
SEARCH_TOOL_CODE = r'''#!/usr/bin/env python3
# Auto-generated helper tool for the Pi research session
import os
import sys
import json
import argparse
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def search_serper(query, max_results=5):
    """Search using Serper.dev Google Search API."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []
    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": max_results}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []
        if "organic" in data:
            for item in data["organic"][:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
        return results
    except Exception as e:
        print(f"[search_tool] Serper search error: {e}", file=sys.stderr)
        return []

def search_duckduckgo(query, max_results=5):
    """Search using DuckDuckGo (free, no API key)."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            ddg_results = ddgs.text(query, max_results=max_results)
            results = []
            for item in ddg_results:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("href", ""),
                    "snippet": item.get("body", "")
                })
            return results
    except Exception as e:
        print(f"[search_tool] DuckDuckGo search error: {e}", file=sys.stderr)
        return []

def web_search(query, max_results=8):
    """Execute web search. Prioritizes Serper (Google), falls back to DuckDuckGo."""
    results = []
    if os.getenv("SERPER_API_KEY"):
        results = search_serper(query, max_results)

    if not results:
        results = search_duckduckgo(query, max_results)

    return results

def fetch_page(url):
    """Fetches a URL and returns cleaned markdown-ish text content."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "nav", "header", "footer", "iframe", "aside", "form", "svg"]):
            element.decompose()
        text_blocks = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre", "code"]):
            tag_name = element.name
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue
            if tag_name.startswith("h"):
                text_blocks.append(f"\n{'#' * int(tag_name[1])} {text}\n")
            elif tag_name == "p":
                text_blocks.append(f"\n{text}\n")
            elif tag_name == "li":
                text_blocks.append(f"- {text}")
            elif tag_name == "table":
                text_blocks.append(f"\n[Table]\n{text}\n")
            elif tag_name in ("pre", "code"):
                text_blocks.append(f"\n```\n{text}\n```\n")
            else:
                text_blocks.append(text)

        final_content = "\n".join(text_blocks)
        words = final_content.split()
        if len(words) > 4000:
            final_content = " ".join(words[:4000]) + "\n\n...[Content Truncated]..."
        return final_content
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search & scrape helper for NIM Research Agent")
    parser.add_argument("--search", type=str, help="Query to search the web")
    parser.add_argument("--scrape", type=str, help="URL to scrape and extract text")
    args = parser.parse_args()
    if args.search:
        print(json.dumps(web_search(args.search), indent=2))
    elif args.scrape:
        print(fetch_page(args.scrape))
    else:
        parser.print_help()
'''

class ResearchAgent:
    def __init__(self, max_steps: int = 12, timeout_seconds: int = 300):
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.project_dir, "node_modules", "@earendil-works", "pi-coding-agent", "dist", "cli.js")

        # Default config paths
        self.config_dir = "/tmp/pi_agent_run_config"
        self.models_path = os.path.join(self.config_dir, "models.json")

    def run(self, query: str, instructions: str = "") -> str:
        """
        Launches the earendil-works/pi coding agent to autonomously perform the research task.
        """
        logger.info(f"Preparing autonomous research workspace for query: '{query}'")

        # 1. Ensure local pi agent exists
        if not os.path.exists(self.cli_path):
            raise FileNotFoundError(
                f"Pi coding agent not found at {self.cli_path}. Please run `npm install @earendil-works/pi-coding-agent` first."
            )

        # 2. Set up models config with NVIDIA NIM compat overrides
        os.makedirs(self.config_dir, exist_ok=True)
        models_data = {
            "providers": {
                "nvidia": {
                    "baseUrl": os.getenv("NVIDIA_NIM_API_BASE", "https://integrate.api.nvidia.com/v1"),
                    "api": "openai-completions",
                    "apiKey": "$NVIDIA_API_KEY",
                    "compat": {
                        "supportsStrictMode": False,
                        "supportsDeveloperRole": False,
                        "supportsReasoningEffort": False
                    },
                    "models": [
                        {"id": "deepseek-ai/deepseek-v4-pro", "input": ["text"]},
                        {"id": "meta/llama-3.3-70b-instruct", "input": ["text"]},
                        {"id": "meta/llama-3.2-90b-vision-instruct", "input": ["text", "image"]}
                    ]
                }
            }
        }
        with open(self.models_path, "w") as f:
            json.dump(models_data, f, indent=2)

        # 3. Initialize research workspace directory
        session_id = str(uuid.uuid4())[:8]
        session_dir = os.path.join(self.project_dir, f"research_run_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        logger.info(f"Session directory created: {session_dir}")

        # 4. Copy search_tool.py helper script to workspace
        search_tool_path = os.path.join(session_dir, "search_tool.py")
        with open(search_tool_path, "w") as f:
            f.write(SEARCH_TOOL_CODE)
        logger.info(f"Copied search_tool.py helper script to workspace")

        # 5. Determine model name
        raw_model = os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro")
        model_name = raw_model if raw_model.startswith("nvidia/") else f"nvidia/{raw_model}"

        # 6. Resolve absolute python path in virtual environment
        python_exec = os.path.join(self.project_dir, ".venv", "bin", "python3")

        # 7. Formulate detailed instructions prompt for the pi agent
        prompt = f"""You are an expert autonomous research agent. Your ONLY task is to perform thorough internet research and write a detailed report.

RESEARCH QUERY: "{query}"
ADDITIONAL INSTRUCTIONS: "{instructions}"

=== TOOLS ===
You have `search_tool.py` in the current directory. Use your bash tool to invoke it.
IMPORTANT: The python path contains spaces. Always wrap it in double quotes:
  "{python_exec}" search_tool.py --search "your query here"
  "{python_exec}" search_tool.py --scrape "https://example.com/page"

The --search command returns a JSON array of results, each with "title", "link", "snippet".
The --scrape command returns the text content of a webpage.

=== MANDATORY WORKFLOW ===
You MUST follow these steps IN ORDER. Do NOT skip any step.

STEP 1: Run 3 different web searches with varied search terms.
  Example: if the topic is "NVIDIA NIM 2025", search for:
  - "NVIDIA NIM microservices 2025 new releases"
  - "NVIDIA NIM performance benchmarks throughput"
  - "NVIDIA NIM supported models deployment"

STEP 2: Collect ALL unique URLs from search results. Save them by running:
  "{python_exec}" -c "urls = ['url1', 'url2', ...]; open('urls.txt','w').write('\\n'.join(urls))"

STEP 3: Scrape AT LEAST 3 of the most relevant URLs (up to 5).
  For EACH url, run: "{python_exec}" search_tool.py --scrape "URL_HERE"
  Read the output carefully. Note the key facts, data points, and quotes.

STEP 4: Write the report file `report.md` using your write tool. The report MUST:
  - Be at least 800 words long
  - Start with `# Title`
  - Have an `## Executive Summary` (2-3 dense paragraphs synthesizing findings)
  - Have 3+ analysis sections (`## Section Name`) with bullet points, data, quotes
  - Use INLINE citations as clickable markdown links throughout the text, like:
    "NIM achieves 2.6x higher throughput ([NVIDIA Blog](https://developer.nvidia.com/blog/actual-article-url))."
  - End with a `## References` section listing every URL you actually scraped:
    1. [Page Title](https://actual-url-you-scraped.com)
    2. [Another Page](https://another-real-url.com)

=== CRITICAL RULES ===
- NEVER fabricate URLs. Only cite URLs you actually received from search results or scraped.
- NEVER write placeholder references like "NVIDIA. NVIDIA NIM. NVIDIA." — always include the full URL.
- If search returns empty results, try different search terms before giving up.
- Read scraped content thoroughly before writing — don't just copy headers.
- The report must contain SPECIFIC facts, numbers, dates, and model names from scraped pages.

Once report.md is written successfully, say "RESEARCH COMPLETE" and stop.
"""


        # 8. Spawn the pi agent process with all required env vars
        env = os.environ.copy()
        env["PI_BEHAVIOR_CONTROL"] = "off"
        env["PI_TELEMETRY"] = "0"
        env["PI_OFFLINE"] = "1"
        env["PI_CODING_AGENT_DIR"] = self.config_dir

        # Forward API keys so search_tool.py can use them
        nvidia_key = os.getenv("NVIDIA_NIM_API_KEY")
        if nvidia_key:
            env["NVIDIA_API_KEY"] = nvidia_key
            env["NVIDIA_NIM_API_KEY"] = nvidia_key

        serper_key = os.getenv("SERPER_API_KEY")
        if serper_key:
            env["SERPER_API_KEY"] = serper_key

        serpapi_key = os.getenv("SERPAPI_API_KEY")
        if serpapi_key:
            env["SERPAPI_API_KEY"] = serpapi_key

        logger.info(f"Spawning pi coding agent in non-interactive print mode using model: {model_name}")
        logger.info(f"Process timeout: {self.timeout_seconds}s | Search APIs: Serper={'yes' if serper_key else 'no'}, DuckDuckGo=fallback")

        try:
            process = subprocess.Popen(
                [
                    "node",
                    self.cli_path,
                    "-p",               # Non-interactive print mode
                    "--no-session",     # Ephemeral session
                    "--model", model_name,
                    prompt
                ],
                cwd=session_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Use a background thread to read stdout so the main thread can enforce timeout
            import threading
            stdout_list = []

            def _read_stdout():
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    sys.stdout.write(f"[Pi Agent] {line}")
                    stdout_list.append(line)
                process.stdout.close()

            reader_thread = threading.Thread(target=_read_stdout, daemon=True)
            reader_thread.start()

            try:
                process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                logger.warning(f"Pi agent timed out after {self.timeout_seconds}s, terminating...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

            reader_thread.join(timeout=5)

            stderr_out = process.stderr.read()
            if stderr_out:
                logger.warning(f"Pi agent stderr:\n{stderr_out[:2000]}")

            if process.returncode != 0 and process.returncode is not None:
                logger.warning(f"Pi coding agent exited with code {process.returncode}")

        except Exception as e:
            logger.error(f"Error executing pi coding agent process: {e}")
            raise e

        # 9. Retrieve report.md
        report_file_path = os.path.join(session_dir, "report.md")
        if not os.path.exists(report_file_path):
            raise FileNotFoundError(
                f"Pi agent completed but did not create 'report.md'. "
                f"Agent output: {''.join(stdout_list[:10])}"
            )

        with open(report_file_path, "r", encoding="utf-8") as f:
            final_report = f.read()

        # 10. Validate report quality (basic sanity check)
        word_count = len(final_report.split())
        if word_count < 50:
            logger.warning(f"Report is suspiciously short ({word_count} words). The agent may not have performed adequate research.")

        # 11. Clean up session directory
        try:
            shutil.rmtree(session_dir)
            logger.info(f"Cleaned up session directory ({word_count} word report)")
        except Exception as clean_err:
            logger.warning(f"Failed to clean up session directory {session_dir}: {clean_err}")

        return final_report
