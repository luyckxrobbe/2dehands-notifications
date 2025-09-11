#!/usr/bin/env python3
"""
Centralized logging configuration that reads from centralized-config.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional


class CentralizedLogger:
    """
    Centralized logging configuration that reads from centralized-config.json
    """
    
    _initialized = False
    _log_level = None
    
    @classmethod
    def load_centralized_config(cls, config_file: str = "configs/centralized-config.json") -> dict:
        """
        Load centralized configuration from JSON file.
        
        Args:
            config_file: Path to the centralized configuration file
            
        Returns:
            Centralized configuration dictionary
        """
        try:
            if Path(config_file).exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config
            else:
                return {}
        except Exception:
            return {}
    
    @classmethod
    def get_log_level(cls) -> str:
        """
        Get the log level from centralized config.
        
        Returns:
            Log level string (DEBUG, INFO, WARNING, ERROR)
        """
        if cls._log_level is None:
            centralized_config = cls.load_centralized_config()
            cls._log_level = centralized_config.get('monitoring', {}).get('log_level', 'INFO')
        
        return cls._log_level
    
    @classmethod
    def setup_logging(cls, 
                     log_file: Optional[str] = None, 
                     format_string: Optional[str] = None,
                     force_level: Optional[str] = None) -> None:
        """
        Set up centralized logging configuration.
        
        Args:
            log_file: Optional log file path (if None, only console logging)
            format_string: Optional custom format string
            force_level: Optional log level to override centralized config
        """
        if cls._initialized:
            return
        
        # Get log level
        if force_level:
            log_level = force_level
        else:
            log_level = cls.get_log_level()
        
        # Convert to numeric level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Default format
        if format_string is None:
            format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure handlers
        handlers = [logging.StreamHandler(sys.stdout)]
        if log_file:
            handlers.append(logging.FileHandler(log_file))
        
        # Configure logging
        logging.basicConfig(
            level=numeric_level,
            format=format_string,
            handlers=handlers,
            force=True  # Override any existing configuration
        )
        
        cls._initialized = True
        
        # Log the configuration
        logger = logging.getLogger(__name__)
        logger.info(f"Centralized logging configured with level: {log_level}")
        if log_file:
            logger.info(f"Log file: {log_file}")
    
    @classmethod
    def update_log_level(cls, new_level: str) -> None:
        """
        Update the log level for all loggers.
        
        Args:
            new_level: New log level (DEBUG, INFO, WARNING, ERROR)
        """
        numeric_level = getattr(logging, new_level.upper(), logging.INFO)
        
        # Update root logger
        logging.getLogger().setLevel(numeric_level)
        
        # Update all handlers
        for handler in logging.getLogger().handlers:
            handler.setLevel(numeric_level)
        
        cls._log_level = new_level
        
        # Log the change
        logger = logging.getLogger(__name__)
        logger.info(f"Log level updated to: {new_level}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger with the centralized configuration.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            Configured logger
        """
        if not cls._initialized:
            cls.setup_logging()
        
        return logging.getLogger(name)


# Convenience function for easy import
def setup_logging(log_file: Optional[str] = None, 
                 format_string: Optional[str] = None,
                 force_level: Optional[str] = None) -> None:
    """
    Convenience function to set up centralized logging.
    
    Args:
        log_file: Optional log file path
        format_string: Optional custom format string  
        force_level: Optional log level to override centralized config
    """
    CentralizedLogger.setup_logging(log_file, format_string, force_level)


def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a centralized logger.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger
    """
    return CentralizedLogger.get_logger(name)
