import os
import base64
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NIMClient:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_NIM_API_KEY")
        self.base_url = os.getenv("NVIDIA_NIM_API_BASE", "https://integrate.api.nvidia.com/v1")
        self.default_model = os.getenv("NVIDIA_MODEL", "deepseek-ai/deepseek-v4-pro")
        self.vision_model = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")

        if not self.api_key:
            raise ValueError("NVIDIA_NIM_API_KEY environment variable is not set. Please set it in your .env file.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        logger.info(f"Initialized NIMClient pointing to {self.base_url}. Default model: {self.default_model}")

    def call_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = 4096,
        stream: bool = False
    ) -> str:
        """
        Calls the chat completions API of the NVIDIA NIM endpoint.
        """
        model_to_use = model or self.default_model
        logger.info(f"Calling chat completion with model {model_to_use}")
        
        try:
            kwargs = {
                "model": model_to_use,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
                
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            
            # Handle potential reasoning content if returned by models like DeepSeek-R1
            # Some platforms return reasoning_content in message attributes
            if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
                reasoning = response.choices[0].message.reasoning_content
                logger.info(f"Received reasoning tokens: {len(reasoning)} chars")
                # We can print it or log it if needed
                
            return content
        except Exception as e:
            logger.error(f"Error calling NIM API model {model_to_use}: {e}")
            raise e

    def call_vision(
        self,
        prompt: str,
        image_path_or_url: str,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        """
        Sends an image along with a prompt to the NIM vision model.
        Supports both local file paths and http/https URLs.
        """
        logger.info(f"Calling vision model {self.vision_model} with image: {image_path_or_url}")
        
        # Prepare the image content block
        image_content = {}
        if image_path_or_url.startswith(("http://", "https://")):
            image_content = {
                "type": "image_url",
                "image_url": {"url": image_path_or_url}
            }
        else:
            # Assume local file path
            if not os.path.exists(image_path_or_url):
                raise FileNotFoundError(f"Local image file not found: {image_path_or_url}")
            
            # Detect mime type
            ext = os.path.splitext(image_path_or_url)[1].lower()
            mime_type = "image/jpeg"
            if ext == ".png":
                mime_type = "image/png"
            elif ext == ".webp":
                mime_type = "image/webp"
            elif ext == ".gif":
                mime_type = "image/gif"
                
            with open(image_path_or_url, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"}
            }

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_content
                ]
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling NIM vision model {self.vision_model}: {e}")
            raise e
