from openai import AsyncOpenAI
from config import config

openai = AsyncOpenAI(
    base_url=config.vector_base_url,
    api_key=config.vector_api_key,
)


async def generate_vector(text: str) -> list[float] | None:
    response = await openai.embeddings.create(
        model=config.vector_model,
        input=[text],
    )
    return response.data[0].embedding
