import logging

from .customer_logging_formatter import CustomLoggingFormatter


class CustomLogging():
    def __init__(self):
        self.formatter = CustomLoggingFormatter(datefmt='%Y-%m-%d %H:%M:%S',
                                                fmt='%(asctime)s.%(msecs)03d %(module)s %(levelname)s: %(message)s',
                                                fixed_length=15)

    def configure_logging(self):
        logger = logging.root
        logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        ch.setFormatter(self.formatter)

        # Add handler to the logger
        logger.addHandler(ch)
