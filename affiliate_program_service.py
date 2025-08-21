from abc import ABC, abstractmethod


class AffiliateProgramService(ABC):
    """
    Base class for affiliate program services that need to execute cron jobs.
    """

    @abstractmethod
    def execute_cron(self) -> None:
        """
        Abstract method to be implemented by subclasses for executing cron jobs.
        This method should contain the logic for periodic affiliate program tasks.
        """
        pass
