"""
    Custom formatter to add color to log messages based on their level.
    This formatter uses ANSI escape sequences to color the log messages
    according to their severity level, making it easier to distinguish
    between different types of log messages in the console.
"""
import logging


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add color to log messages based on their level."""

    # ANSI escape sequences for colors
    # These are used to color the log messages based on their severity level
    # DEBUG: Cyan, INFO: Green, WARNING: Yellow, ERROR: Red, CRITICAL: Magenta
    LEVEL_COLORS = {
        logging.DEBUG: "\x1b[36m",     # Cyan
        logging.INFO: "\x1b[32m",      # Green
        logging.WARNING: "\x1b[33m",   # Yellow
        logging.ERROR: "\x1b[31m",     # Red
        logging.CRITICAL: "\x1b[35m",  # Magenta
    }
    RESET = "\x1b[0m"

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, "")
        formatted = super().format(record)
        return f"{color}{formatted}{self.RESET}"
