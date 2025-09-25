from constants import PROMPT_SPLIT_JOINER
from xai_sdk import Client
from xai_sdk.chat import user
from enums import LlmErrorPrompt
from logger_service import LoggerService

from common import os, load_dotenv


class LlmService:
    def __init__(self, model_name: str = "grok-3-mini"):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.model_name = model_name
        self.x_client = Client(api_key=os.getenv("XAI_API_KEY"))

    def generate_text(
        self,
        prompt: str,
        retry_count: int = 1,
    ) -> str:
        try:
            chat = self.x_client.chat.create(model=self.model_name)
            prompt_splits = [
                f"Respond with {LlmErrorPrompt.QUOTA_EXCEEDED} if no more credit for usage",
                f"Respond with {LlmErrorPrompt.LENGTH_EXCEEDED} if input + output length is too long. {prompt}",
                f"Do not include prompt in the response",
            ]
            prompt = PROMPT_SPLIT_JOINER.join(prompt_splits)
            chat = self.x_client.chat.create(model=self.model_name)
            chat.append(user(prompt))
            response = chat.sample()

            if LlmErrorPrompt.QUOTA_EXCEEDED in response.content.lower():
                if retry_count > 0:
                    self.logger.warning(
                        f"Quota exceeded, retrying... ({retry_count} retries left)"
                    )
                    return self.generate_text(prompt, retry_count=retry_count - 1)
                raise LlmErrorPrompt.QUOTA_EXCEEDED

            if LlmErrorPrompt.LENGTH_EXCEEDED in response.content.lower():
                if retry_count > 0:
                    self.logger.warning(
                        f"Length exceeded, retrying... ({retry_count} retries left)"
                    )
                    return self.generate_text(prompt, retry_count=retry_count - 1)
                raise LlmErrorPrompt.LENGTH_EXCEEDED

            return response.content
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"LLM API error: {error_message}")
