from writer import generate_text
import asyncio

async def main():
    print(
        await generate_text(
            messages=[
                {"role": "user", "content": "你好"},
            ]
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
