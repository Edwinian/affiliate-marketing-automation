import os
from xai_sdk import Client
from xai_sdk.chat import user
from dotenv import load_dotenv

load_dotenv()  # Loads the .env file


class LlmService:
    def __init__(self, model_name: str = "grok-3-mini"):
        self.model_name = model_name
        self.x_client = Client(api_key=os.getenv("XAI_API_KEY"))

    def generate_text(
        self,
        prompt: str,
    ) -> str:
        chat = self.x_client.chat.create(model=self.model_name)
        chat.append(user(prompt))
        response = chat.sample()
        print(f"LLM response generated")
        return response.content
