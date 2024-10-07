import logging


class CustomLoggingFormatter(logging.Formatter):
    def __init__(self, fixed_length=20, *args, **kwargs):
        self.fixed_length = fixed_length
        super().__init__(*args, **kwargs)

    def format(self, record):
        # Format the module name to ensure it is exactly fixed_length characters
        record.module = f"{record.module:<{self.fixed_length}}"[
                        :self.fixed_length]  # Pad with spaces and truncate if necessary
        return super().format(record)

