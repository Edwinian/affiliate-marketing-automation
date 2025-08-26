import logging


class LoggerService:
    PREFIX: str = None

    def __init__(self, name: str, level: int = logging.INFO):
        """Initialize the logger with a name and default level."""
        self.log_name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()  # Outputs to stdout for AWS CloudWatch
            formatter = logging.Formatter("%(levelname)s %(name)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def set_prefix(self, prefix: str) -> None:
        self.PREFIX = prefix

    def _get_message_with_prefix(self, message: str):
        return f"{self.PREFIX}: {message}" if self.PREFIX else message

    def info(self, message: str) -> None:
        """Log results"""
        self.logger.info(self._get_message_with_prefix(message))

    def warning(self, message: str) -> None:
        self.logger.warning(self._get_message_with_prefix(message))

    def error(self, message: str) -> None:
        self.logger.error(self._get_message_with_prefix(message))


if __name__ == "__main__":
    service = LoggerService(name="ERROR TEST")
