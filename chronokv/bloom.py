"""
ChronoKV: Bitarray-Backed Bloom Filter with Mathematical Optimization.

Theoretical Background:
A Bloom filter (Bloom, 1970) is a space-efficient probabilistic data structure used to test
whether an element is a member of a set. False positive matches are possible, but false
negatives are mathematically impossible:
- contains(x) == False => x is guaranteed NOT to be in the set.
- contains(x) == True  => x is PROBABLY in the set (with error probability ε).

Mathematical Derivation:
Given:
- n: Expected number of items to insert.
- ε: Target false positive probability (e.g., 0.01 for 1%).

1. Optimal number of bits m:
   m = - (n * ln(ε)) / (ln(2)^2)
     = - (n * ln(ε)) / 0.4804530139182014

2. Optimal number of hash functions k:
   k = (m / n) * ln(2)

3. Kirsch-Mitzenmacher Double-Hashing Technique (2006):
   Instead of computing k independent cryptographic hashes, we derive:
   g_i(x) = (h1(x) + i * h2(x)) mod m   for i in [0 .. k-1]
   where h1 and h2 are derived from Murmur/FNV-1a 64-bit hash splits.
   This guarantees asymptotic equivalence to k independent hash functions with zero performance penalty.
"""

from __future__ import annotations
import math
import struct
import zlib
from typing import Tuple


def fnv1a_64(data: bytes) -> int:
    """Computes a 64-bit FNV-1a hash."""
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


class BloomFilter:
    """
    Pure Python bitarray-backed Bloom filter.
    """
    def __init__(self, expected_elements: int = 1000, false_positive_rate: float = 0.01) -> None:
        self.expected_elements = max(1, expected_elements)
        self.false_positive_rate = max(1e-6, min(0.5, false_positive_rate))

        # Calculate optimal m and k
        self.num_bits = self._calculate_optimal_bits(self.expected_elements, self.false_positive_rate)
        self.num_hashes = self._calculate_optimal_hashes(self.num_bits, self.expected_elements)

        # Allocate bytearray: ceil(num_bits / 8) bytes
        self.num_bytes = (self.num_bits + 7) // 8
        self.bit_array = bytearray(self.num_bytes)
        self.elements_added = 0

    @staticmethod
    def _calculate_optimal_bits(n: int, fp_rate: float) -> int:
        """m = - (n * ln(p)) / (ln(2)^2)"""
        m = - (n * math.log(fp_rate)) / (math.log(2) ** 2)
        return max(64, int(math.ceil(m)))

    @staticmethod
    def _calculate_optimal_hashes(m: int, n: int) -> int:
        """k = (m / n) * ln(2)"""
        k = (m / n) * math.log(2)
        return max(1, min(30, int(round(k))))

    def _get_hashes(self, key: bytes) -> Tuple[int, int]:
        """
        Derives two distinct 64-bit hashes h1 and h2 using FNV-1a and CRC32 + bit manipulation.
        """
        h1 = fnv1a_64(key)
        # Combine CRC32 with secondary FNV step for h2
        crc = zlib.crc32(key) & 0xFFFFFFFF
        h2 = ((h1 >> 32) ^ (crc * 0x5bd1e995)) & 0xFFFFFFFFFFFFFFFF
        if h2 == 0:
            h2 = 0x9e3779b97f4a7c15  # Non-zero constant golden ratio
        return h1, h2

    def add(self, key: bytes) -> None:
        """
        Inserts a key into the Bloom filter.
        
        Complexity:
            Time: O(k) bit operations, where k is typically 4 to 10.
            Space: O(1) auxiliary memory.
        """
        h1, h2 = self._get_hashes(key)
        for i in range(self.num_hashes):
            bit_index = (h1 + i * h2) % self.num_bits
            byte_idx = bit_index >> 3       # bit_index // 8
            bit_in_byte = bit_index & 0x07   # bit_index % 8
            self.bit_array[byte_idx] |= (1 << bit_in_byte)

        self.elements_added += 1

    def contains(self, key: bytes) -> bool:
        """
        Tests if a key may be in the set.
        
        Returns:
            False: Key is guaranteed NOT in the set (0% false negative rate).
            True:  Key is PROBABLY in the set (with <= target FP rate).
        """
        h1, h2 = self._get_hashes(key)
        for i in range(self.num_hashes):
            bit_index = (h1 + i * h2) % self.num_bits
            byte_idx = bit_index >> 3
            bit_in_byte = bit_index & 0x07
            if not (self.bit_array[byte_idx] & (1 << bit_in_byte)):
                return False
        return True

    def bits_set_count(self) -> int:
        """Counts total number of bits set to 1."""
        return sum(bin(byte).count("1") for byte in self.bit_array)

    def current_false_positive_rate(self) -> float:
        """
        Calculates empirical false positive rate based on current fill factor:
        P = (1 - e^(-k * n / m))^k
        """
        if self.num_bits == 0 or self.elements_added == 0:
            return 0.0
        exp_term = math.exp(- (self.num_hashes * self.elements_added) / self.num_bits)
        return (1.0 - exp_term) ** self.num_hashes

    def to_bytes(self) -> bytes:
        """
        Serializes the Bloom filter to binary format:
        [NumBits: 8B uint64 | NumHashes: 4B uint32 | ElementsAdded: 4B uint32 | BitArray: N bytes]
        """
        header = struct.pack(">QII", self.num_bits, self.num_hashes, self.elements_added)
        return header + bytes(self.bit_array)

    @classmethod
    def from_bytes(cls, data: bytes) -> BloomFilter:
        """Deserializes a BloomFilter instance from binary bytes."""
        header_size = struct.calcsize(">QII")
        num_bits, num_hashes, elements_added = struct.unpack(">QII", data[:header_size])
        
        bf = cls.__new__(cls)
        bf.num_bits = num_bits
        bf.num_hashes = num_hashes
        bf.elements_added = elements_added
        bf.num_bytes = (num_bits + 7) // 8
        bf.bit_array = bytearray(data[header_size:header_size + bf.num_bytes])
        bf.expected_elements = elements_added
        bf.false_positive_rate = 0.01
        return bf
