"""Where the festival lives. The rest of the program only knows load/save."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from deauville.errors import InvalidError, NotFoundError
from deauville.festival import Festival, festival_from_data


class Storage(ABC):
    """Load and save a festival. JSON on disk is one implementation."""

    @abstractmethod
    def load(self) -> Festival:
        """Return the current festival."""

    @abstractmethod
    def save(self, festival: Festival) -> None:
        """Persist the festival."""


class JsonStorage(Storage):
    """A festival.json file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> Festival:
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise NotFoundError(f"{self.path} was not found.") from None
        except json.JSONDecodeError as error:
            raise InvalidError(
                f"{self.path} is damaged (line {error.lineno})."
            ) from None
        return festival_from_data(data)

    def save(self, festival: Festival) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(festival.to_data(), file, ensure_ascii=False, indent=2)
            file.write("\n")


class MemoryStorage(Storage):
    """Nothing on disk: handy for tests."""

    def __init__(self, festival: Festival) -> None:
        self._festival = festival

    def load(self) -> Festival:
        return self._festival

    def save(self, festival: Festival) -> None:
        self._festival = festival
