import asyncio
from project_instant import ProjectInstant
import project_instant


async def main():
    instant = ProjectInstant("测试项目")
    await instant.initialize()
    await project_instant.save_to_directory(instant)


if __name__ == "__main__":
    asyncio.run(main())
