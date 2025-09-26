from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    writer_api_key: str
    writer_base_url: str | None
    writer_model: str
    vector_api_key: str
    vector_base_url: str | None
    vector_model: str
    vector_dimension: int

    @classmethod
    def from_env(cls) -> "Config":
        writer_api_key = os.getenv("WRITER_API_KEY")
        if not writer_api_key:
            raise ValueError("WRITER_API_KEY is not set in environment variables")
        vector_api_key = os.getenv("VECTOR_API_KEY")
        if not vector_api_key:
            raise ValueError("VECTOR_API_KEY is not set in environment variables")
        vector_dimension = os.getenv("VECTOR_DIMENSION")
        if not vector_dimension:
            raise ValueError("VECTOR_DIMENSION is not set in environment variables")
        vector_dimension_int = int(vector_dimension)

        return cls(
            writer_base_url=os.getenv("WRITER_BASE_URL"),
            writer_api_key=writer_api_key,
            writer_model=os.getenv("WRITER_MODEL", "gpt-4.1"),
            vector_base_url=os.getenv("VECTOR_BASE_URL"),
            vector_api_key=vector_api_key,
            vector_model=os.getenv("VECTOR_MODEL", "nomic-embed-text"),
            vector_dimension=vector_dimension_int,
        )


config = Config.from_env()
