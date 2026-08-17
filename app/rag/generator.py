from collections.abc import Sequence


class Generator:
    """Answer generation interface."""

    def generate(self, question: str, context: Sequence[str]) -> str:
        raise NotImplementedError
