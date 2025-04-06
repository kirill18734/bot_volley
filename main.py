#main.py
import asyncio
from bot.bot_runner import BotRunner
from config.config import config


async def main():
    bot_runner = BotRunner(
        token=config.BOT_TOKEN
    )
    await bot_runner.run()

if __name__ == "__main__":
    asyncio.run(main())
