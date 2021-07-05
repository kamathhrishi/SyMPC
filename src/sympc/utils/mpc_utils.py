"""Multi-Party Computation utils."""

# stdlib
from functools import lru_cache
from typing import List
from typing import Union

# third party
# TODO: Remove this
import torch
import torchcsprng as csprng  # type: ignore

RING_SIZE_TO_TYPE = {
    2 ** 1: torch.bool,
    2 ** 8: torch.int8,
    2 ** 16: torch.int16,
    2 ** 32: torch.int32,
    2 ** 64: torch.int64,
}
TYPE_TO_RING_SIZE = {
    torch.bool: 2 ** 1,
    torch.int8: 2 ** 8,
    torch.int16: 2 ** 16,
    torch.int32: 2 ** 32,
    torch.int64: 2 ** 64,
}


def count_wraps(share_list: List[torch.tensor]) -> torch.Tensor:
    """Count overflows and underflows if we reconstruct the original value.

    This function is taken from the CrypTen project.
    CrypTen repository: https://github.com/facebookresearch/CrypTen

    Args:
        share_list (List[ShareTensor]): List of the shares.

    Returns:
        torch.Tensor: The number of wraparounds.
    """
    res = torch.zeros(size=share_list[0].size(), dtype=torch.long)
    prev_share = share_list[0]
    for cur_share in share_list[1:]:
        next_share = cur_share + prev_share

        # If prev and current shares are negative,
        # but the result is positive then is an underflow
        res -= ((prev_share < 0) & (cur_share < 0) & (next_share > 0)).long()

        # If prev and current shares are positive,
        # but the result is positive then is an overflow
        res += ((prev_share > 0) & (cur_share > 0) & (next_share < 0)).long()
        prev_share = next_share

    return res


@lru_cache(maxsize=len(RING_SIZE_TO_TYPE))
def get_type_from_ring(ring_size: int) -> torch.dtype:
    """Type of a tensor given a ring size/field.

    Args:
        ring_size (int): Ring size.

    Returns:
        torch.dtype: Type of tensor.

    Raises:
        ValueError: If Ring size not in `RING_SIZE_TO_TYPE.keys()`.
    """
    if ring_size not in RING_SIZE_TO_TYPE:
        raise ValueError(f"Ring size should be in {RING_SIZE_TO_TYPE.keys()}")

    return RING_SIZE_TO_TYPE[ring_size]


@lru_cache(maxsize=len(TYPE_TO_RING_SIZE))
def get_ring_size_from_type(dtype: torch.dtype) -> int:
    """Ring size of tensor given dtype.

    Args:
        dtype (torch.dtype): Torch data

    Returns:
        int: Ring size of type

    Raises:
        ValueError: If Torch size not in `TYPE_TO_RING_SIZE.keys()`.
    """
    if dtype not in TYPE_TO_RING_SIZE:
        raise ValueError(f"Torch type should be in {TYPE_TO_RING_SIZE.keys()}")

    return TYPE_TO_RING_SIZE[dtype]


def get_new_generator(seed: int) -> torch.Generator:
    """Get a generator that is initialized with seed.

    Args:
        seed (int): Seed.

    Returns:
        torch.Generator: Generator.
    """
    # TODO: this is not crypto secure, but it lets you add a seed
    return csprng.create_mt19937_generator(seed=seed)


def generate_random_element(
    tensor_type: torch.dtype,
    generator: torch.Generator,
    shape: Union[tuple, torch.Size],
    device: str = "cpu",
) -> torch.Tensor:
    """Generate a new "random" tensor.

    Args:
        tensor_type (torch.dtype): Type of the tensor.
        generator (torch.Generator): Torch Generator.
        shape (Union[tuple, torch.Size]): Shape.
        device (str): Device value. Defaults to cpu.

    Returns:
        torch.Tensor: Random tensor.
    """
    return torch.empty(size=shape, dtype=tensor_type, device=device).random_(
        generator=generator
    )


@lru_cache()
def get_nr_bits(ring_size: int) -> int:
    """Get number of bits.

    Args:
        ring_size (int): Ring Size.

    Returns:
        int: Bit length.
    """
    return (ring_size - 1).bit_length()


def decompose(
    tensor: torch.Tensor, ring_size: int, shape: Union[tuple, torch.Size] = None
) -> torch.Tensor:
    """Decompose a tenstor into its binary representation.

    Args:
        tensor (torch.Tensor): Tensor to decompose.
        ring_size (int): Ring size.
        shape (Union[tuple, torch.Size]): Shape.

    Returns:
        torch.Tensor: Tensor in binary.
    """
    tensor_type = get_type_from_ring(ring_size)

    nr_bits = get_nr_bits(ring_size)
    powers = torch.arange(nr_bits, dtype=tensor_type)

    if shape is None:
        shape = tensor.shape

    for _ in range(len(shape)):
        powers = powers.unsqueeze(0)

    tensor = tensor.unsqueeze(-1)
    moduli = (2 ** powers).to(tensor_type)
    tensor = torch.fmod(tensor / moduli, 2).to(tensor_type)
    return tensor
