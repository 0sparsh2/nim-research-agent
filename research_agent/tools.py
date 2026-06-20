import os
import requests
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ddgs import DDGS
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

def search_serpapi(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search using SerpAPI.
    """
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPER_API_KEY")
    if not api_key:
        return []
    
    url = "https://serpapi.com/search.json"
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": max_results
    }
    
    try:
        logger.info(f"Searching SerpAPI for: '{query}'")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        if "organic_results" in data:
            for item in data["organic_results"][:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", item.get("snippet_highlighted_words", ""))
                })
        return results
    except Exception as e:
        logger.error(f"SerpAPI search failed: {e}")
        return []

def search_serper(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search using Serper API.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []
    
    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": max_results
    }
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Searching Serper for: '{query}'")
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
        logger.error(f"Serper search failed: {e}")
        return []

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search using DuckDuckGo (free, no API key).
    """
    try:
        logger.info(f"Searching DuckDuckGo for: '{query}'")
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
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Execute web search, prioritizing SerpAPI, then Serper, and falling back to DuckDuckGo.
    """
    results = []
    if os.getenv("SERPAPI_API_KEY"):
        results = search_serpapi(query, max_results)
    
    if not results and os.getenv("SERPER_API_KEY"):
        results = search_serper(query, max_results)
        
    if not results:
        results = search_duckduckgo(query, max_results)
        
    return results

def fetch_page(url: str) -> str:
    """
    Fetches the HTML of a webpage and returns a cleaned markdown-like text content.
    """
    try:
        logger.info(f"Scraping webpage: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return f"Error: Failed to fetch the URL due to: {e}"

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove noisy tags
        for element in soup(["script", "style", "nav", "header", "footer", "iframe", "aside", "form", "svg"]):
            element.decompose()
            
        # Get textual content
        text_blocks = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre", "code"]):
            tag_name = element.name
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue
                
            if tag_name.startswith("h"):
                level = tag_name[1]
                text_blocks.append(f"\n{'#' * int(level)} {text}\n")
            elif tag_name == "p":
                text_blocks.append(f"\n{text}\n")
            elif tag_name == "li":
                text_blocks.append(f"- {text}")
            elif tag_name == "table":
                text_blocks.append(f"\n[Table content]\n{text}\n")
            elif tag_name in ("pre", "code"):
                text_blocks.append(f"\n```\n{text}\n```\n")
            else:
                text_blocks.append(text)
                
        cleaned_text = "\n".join(text_blocks)
        
        # Normalize whitespace
        lines = [line.strip() for line in cleaned_text.split("\n")]
        cleaned_lines = []
        for line in lines:
            if line:
                cleaned_lines.append(line)
            elif not cleaned_lines or cleaned_lines[-1] != "":
                cleaned_lines.append("")
                
        final_content = "\n".join(cleaned_lines)
        
        words = final_content.split()
        max_words = 12000
        if len(words) > max_words:
            logger.info(f"Truncated scraped content from {len(words)} to {max_words} words.")
            final_content = " ".join(words[:max_words]) + "\n\n...[Content Truncated]..."
            
        return final_content
        
    except Exception as e:
        logger.error(f"Error parsing HTML from {url}: {e}")
        return f"Error: Failed to parse page content: {e}"

def download_image(url: str, output_dir: str = "/tmp") -> Optional[str]:
    """
    Downloads an image from a URL to a local temporary path.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        filename = url.split("/")[-1].split("?")[0]
        if not filename or not any(filename.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]):
            filename = "temp_image.png"
            
        filepath = os.path.join(output_dir, filename)
        logger.info(f"Downloading image from {url} to {filepath}")
        
        response = requests.get(url, headers=HEADERS, stream=True, timeout=15)
        response.raise_for_status()
        
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filepath
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
        return None
