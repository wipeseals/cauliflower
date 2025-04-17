from log import error, warn, trace, debug, info, LogLevel
from nand import NandConfig, NandBlockManager, PageCodec, get_driver


def main() -> None:
    nandio, nandcmd = get_driver(keep_wp=False)
    blockmng = NandBlockManager(nandcmd=nandcmd)
    codec = PageCodec(scramble_seed=0xA5, use_scramble=True, use_ecc=True, use_crc=True)
    pass


if __name__ == "__main__":
    main()
