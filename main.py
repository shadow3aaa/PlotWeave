from writer import generate_text
import asyncio
from world import World


async def main():
    world = World()

    print(
        await generate_text(
            messages=[
                {"role": "user", "content": f"总结{world}"},
            ]
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
