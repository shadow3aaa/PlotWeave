from typing import Iterable
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from dotenv import load_dotenv
from config import config

load_dotenv()

openai = AsyncOpenAI(
    base_url=config.writer_base_url,
    api_key=config.writer_api_key,
)


async def generate_text(messages: Iterable[ChatCompletionMessageParam]) -> str:
    response = await openai.chat.completions.create(
        model=config.writer_model,
        messages=messages,
    )
    return response.choices[0].message.content
