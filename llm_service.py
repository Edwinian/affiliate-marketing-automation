import os
from sentence_transformers import SentenceTransformer, util
from xai_sdk import Client
from xai_sdk.chat import user
from dotenv import load_dotenv

load_dotenv()  # Loads the .env file


class LlmService:
    def __init__(self, model_name: str = "grok-3-mini"):
        self.model_name = model_name
        self.x_client = Client(api_key=os.getenv("XAI_API_KEY"))
        self.sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")

    def generate_text(
        self,
        prompt: str,
    ) -> str:
        chat = self.x_client.chat.create(model=self.model_name)
        chat.append(user(prompt))
        response = chat.sample()
        print(f"LLM response generated")
        return response.content

    def get_similarity_score(
        self,
        text1: str,
        text2: str,
    ) -> float:
        embeddings1 = self.sentence_transformer.encode(text1, convert_to_tensor=True)
        embeddings2 = self.sentence_transformer.encode(text2, convert_to_tensor=True)
        similarity = util.cos_sim(embeddings1, embeddings2)[0][0]
        return similarity
