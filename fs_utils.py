import asyncio
from pathlib import Path
from typing import AsyncGenerator


async def async_rglob(
    root: str | Path,
    pattern: str = "*",
) -> AsyncGenerator[Path, None]:
    """
    异步递归遍历目录，返回匹配到的文件路径。

    - root: 起始目录
    - pattern: 匹配模式，默认为 "*"（所有文件）
    """
    root = Path(root)

    loop = asyncio.get_running_loop()
    files = await loop.run_in_executor(None, lambda: list(root.rglob(pattern)))

    for file in files:
        yield file
