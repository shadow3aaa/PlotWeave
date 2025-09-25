from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    writer_api_key: str
    writer_base_url: str | None
    writer_model: str

    @classmethod
    def from_env(cls) -> "Config":
        writer_api_key = os.getenv("WRITER_API_KEY")
        if not writer_api_key:
            raise ValueError("WRITER_API_KEY is not set in environment variables")

        return cls(
            writer_base_url=os.getenv("WRITER_BASE_URL"),
            writer_api_key=writer_api_key,
            writer_model=os.getenv("WRITER_MODEL", "gpt-4.1"),
        )


config = Config.from_env()
