from typing import Optional
from constants import PROMPT_SPLIT_JOINER
from xai_sdk import Client
from xai_sdk.chat import user, image
from enums import LlmErrorPrompt
from logger_service import LoggerService

from common import os, load_dotenv

class LlmService:
    def __init__(self):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.x_client = Client(api_key=os.getenv("XAI_API_KEY"))
        self.TEXT_MODEL = "grok-3-mini"
        self.VISION_MODEL = "grok-4-fast-non-reasoning"

    def _get_response_content(self, chat) -> str:
        response = chat.sample()
        content = response.content
        if LlmErrorPrompt.QUOTA_EXCEEDED in content.lower():
            raise LlmErrorPrompt.QUOTA_EXCEEDED
        if LlmErrorPrompt.LENGTH_EXCEEDED in content.lower():
            raise LlmErrorPrompt.LENGTH_EXCEEDED
        return content
    
    def _get_prompt(self, prompt_splits: list[str]) -> str:
        base_prompt_splits = [
            f"Respond with {LlmErrorPrompt.QUOTA_EXCEEDED} if no more credit for usage", 
            f"Respond with {LlmErrorPrompt.LENGTH_EXCEEDED} if input + output length is too long", 
            f"Do not include prompt in the response"
        ]
        prompt = PROMPT_SPLIT_JOINER.join(base_prompt_splits + prompt_splits)
        return prompt
    
    def generate_text(
        self,
        prompt: str,
    ) -> str:
        try:
            chat = self.x_client.chat.create(model=self.TEXT_MODEL)
            prompt = self._get_prompt([prompt])
            chat.append(user(prompt))
            return self._get_response_content(chat)
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"LLM API error: {error_message}")

    def detect_image_items(self, image_url: str, limit: Optional[int] = None) -> list[str]:
            try:
                chat = self.x_client.chat.create(model=self.VISION_MODEL)
                prompt_splits = [
                    "What are the items in this image?",
                    "Return the items only",
                    "Return the items in title case separated by commas",
                    "Return the items in order of focus from most focused to least focused",
                ]
                prompt = self._get_prompt(prompt_splits)
                chat.append(user(prompt, image(image_url=image_url, detail="low")))
                content = self._get_response_content(chat)
                item_list = content.split(",")
                return item_list[:limit or len(item_list)]
            except Exception as e:
                error_message = str(e)
                self.logger.error(f"LLM API error: {error_message}")

if __name__ == "__main__":
    service = LlmService()
    image_url = "https://images.pexels.com/photos/32753786/pexels-photo-32753786.jpeg"
    result = service.detect_image_items(image_url=image_url)
    print(result)