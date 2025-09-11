#!/usr/bin/env python3
"""
Telegram Bot for sending messages
"""

import asyncio
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str):
        """
        Initialize the Telegram bot
        
        Args:
            token (str): Bot token from BotFather
        """
        self.bot = Bot(token=token)
        self.token = token
    
    async def send_message(self, chat_id: str, message: str, parse_mode: str = None) -> bool:
        """
        Send a message to a specific chat
        
        Args:
            chat_id (str): Chat ID to send message to
            message (str): Message content to send
            parse_mode (str, optional): Parse mode (HTML, Markdown, etc.)
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info(f"Message sent successfully to chat {chat_id}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    async def send_message_to_multiple_chats(self, chat_ids: list, message: str, parse_mode: str = None) -> dict:
        """
        Send a message to multiple chats
        
        Args:
            chat_ids (list): List of chat IDs to send message to
            message (str): Message content to send
            parse_mode (str, optional): Parse mode (HTML, Markdown, etc.)
            
        Returns:
            dict: Results for each chat ID
        """
        results = {}
        
        for chat_id in chat_ids:
            success = await self.send_message(chat_id, message, parse_mode)
            results[chat_id] = success
        
        return results
    
    async def get_bot_info(self) -> dict:
        """
        Get information about the bot
        
        Returns:
            dict: Bot information
        """
        try:
            bot_info = await self.bot.get_me()
            return {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'can_join_groups': bot_info.can_join_groups,
                'can_read_all_group_messages': bot_info.can_read_all_group_messages,
                'supports_inline_queries': bot_info.supports_inline_queries
            }
        except TelegramError as e:
            logger.error(f"Failed to get bot info: {e}")
            return {}


async def main():
    """
    Main function to demonstrate bot usage
    """
    # Get bot token from environment variable
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        logger.error("Please create a .env file with your bot token")
        logger.error("Copy env_template.txt to .env and fill in your values")
        return
    
    # Initialize bot
    bot = TelegramBot(bot_token)
    
    # Get bot information
    logger.info("Getting bot information...")
    bot_info = await bot.get_bot_info()
    if bot_info:
        logger.info(f"Bot: @{bot_info.get('username', 'Unknown')} ({bot_info.get('first_name', 'Unknown')})")
        logger.info(f"Bot ID: {bot_info.get('id', 'Unknown')}")
    
    # Example usage - you can modify these values
    chat_id = os.getenv('TELEGRAM_CHAT_ID', 'your_chat_id_here')
    message = "Hello! This is a test message from your Telegram bot."
    
    if chat_id == 'your_chat_id_here':
        logger.info("\nTo send a message, set the TELEGRAM_CHAT_ID in your .env file")
        logger.info("You can find your chat ID by messaging @userinfobot on Telegram")
        return
    
    # Send message
    logger.info(f"\nSending message to chat {chat_id}...")
    success = await bot.send_message(chat_id, message)
    
    if success:
        logger.info("Message sent successfully!")
    else:
        logger.error("Failed to send message")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
