from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    writer_api_key: str
    writer_base_url: str
    writer_model: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            writer_base_url=os.getenv("WRITER_BASE_URL"),
            writer_api_key=os.getenv("WRITER_API_KEY"),
            writer_model=os.getenv("WRITER_MODEL"),
        )

config = Config.from_env()
