"""Register images of SunSpec devices for tests."""

from collections.abc import Sequence

SUNS = [0x5375, 0x6E53]


def model(model_id: int, body: Sequence[int]) -> list[int]:
    """Registers of one model: id, length, body."""
    return [model_id, len(body), *body]


def image(base: int, *models: list[int]) -> dict[int, int]:
    """Device registers by address: marker at ``base``, the models, end marker."""
    registers = [*SUNS, *(word for m in models for word in m), 0xFFFF, 0]
    return {base + i: word for i, word in enumerate(registers)}


def reader(registers: dict[int, int], requests: list | None = None):
    """Async read function over ``registers``; addresses not in the image fail like an error response."""

    async def read(address: int, count: int) -> list[int] | None:
        if requests is not None:
            requests.append((address, count))
        if any(a not in registers for a in range(address, address + count)):
            return None
        return [registers[a] for a in range(address, address + count)]

    return read
