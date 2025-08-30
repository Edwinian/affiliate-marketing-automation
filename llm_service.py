from xai_sdk import Client
from xai_sdk.chat import user
from enums import LlmErrorPrompt
from logger_service import LoggerService

from common import os, load_dotenv


class InsufficientCreditsError(Exception):
    """Exception raised when there are insufficient credits for the API call."""

    pass


class LlmService:
    def __init__(self, model_name: str = "grok-3-mini"):
        self.logger = LoggerService(name=self.__class__.__name__)
        self.model_name = model_name
        self.x_client = Client(api_key=os.getenv("XAI_API_KEY"))

    def generate_text(
        self,
        prompt: str,
    ) -> str:
        try:
            prompt = f"Respond with {LlmErrorPrompt.QUOTA_EXCEEDED} if no more credit for usage. Respond with {LlmErrorPrompt.LENGTH_EXCEEDED} if input + output length is too long. {prompt}"
            chat = self.x_client.chat.create(model=self.model_name)
            chat.append(user(prompt))
            response = chat.sample()

            if LlmErrorPrompt.QUOTA_EXCEEDED in response.content.lower():
                raise InsufficientCreditsError(LlmErrorPrompt.QUOTA_EXCEEDED)

            if LlmErrorPrompt.LENGTH_EXCEEDED in response.content.lower():
                return LlmErrorPrompt.LENGTH_EXCEEDED

            return response.content
        except Exception as e:
            error_message = str(e)
            self.logger.error(f"LLM API error: {error_message}")
