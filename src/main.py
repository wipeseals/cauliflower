import sys
import json
from log import error, trace, debug, info, LogLevel
from nand import NandConfig, NandBlockManager, PageCodec, get_driver


############################################################################
# Main
############################################################################


def test_readid(num_cs: int = 2) -> None:
    """READ ID"""
    nandio, nandcmd = get_driver(keep_wp=False)
    for i in range(num_cs):
        ret = nandcmd.read_id(i)
        info(f"CS{i}: {ret}")


def test_erase_program_read() -> None:
    nandio, nandcmd = get_driver(keep_wp=False)
    blockmng = NandBlockManager(nandcmd=nandcmd)
    block = blockmng.alloc()
    debug(f"Allocated Block: {block}")

    read_data0 = blockmng.read(cs_index=0, block=block, page=0)
    assert read_data0 is not None
    debug(f"Read Data: {read_data0.hex()}")

    write_data = bytearray([(x * 2) & 0xFF for x in range(NandConfig.PAGE_ALL_BYTES)])
    is_ok = blockmng.program(cs_index=0, block=block, page=0, data=write_data)
    debug(f"Program Result: {is_ok}")

    read_data1 = blockmng.read(cs_index=0, block=block, page=0)
    assert read_data1 is not None
    debug(f"Read Data: {read_data1.hex()}")
    debug(f"Data Match: {read_data1 == write_data}")


def test_codec() -> None:
    nandio, nandcmd = get_driver(keep_wp=False)
    blockmng = NandBlockManager(nandcmd=nandcmd)
    codec = PageCodec(scramble_seed=0xA5, use_scramble=True, use_ecc=True, use_crc=True)

    write_data = bytearray(
        [(x * 2) & 0xFF for x in range(NandConfig.PAGE_USABLE_BYTES)]
    )
    write_data_enc = codec.encode(write_data)
    debug(f"Write Data: {write_data.hex()}")
    debug(f"Write Data Encoded: {write_data_enc.hex()}")

    write_data_dec = codec.decode(write_data_enc)
    debug(f"Write Data Decoded: {write_data_dec.hex()}")
    assert write_data == write_data_dec


import os


def main() -> None:
    test_readid()
    test_erase_program_read()
    test_codec()
    print(os.listdir())


if __name__ == "__main__":
    main()
