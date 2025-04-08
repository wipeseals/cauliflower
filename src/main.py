import sys
import json
from log import error, trace, debug, info, LogLevel
from nand import NandConfig, NandBlockManager, PageCodec, get_driver


############################################################################
# Main
############################################################################


def test_readid(num_chip: int = 2) -> None:
    """READ ID"""
    nandio, nandcmd = get_driver(keep_wp=False)
    for i in range(num_chip):
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


class Ecc:
    @staticmethod
    def gen_hamming_matrix(n: int, k: int) -> list[int]:
        """
        拡張ハミング符号の生成行列を生成する
        n: 符号長 (2^m)
        k: データ長 (n - m - 1)
        """
        # 符号長 n のビット数 m を計算
        m = 0
        while (1 << m) < n:
            m += 1
        if (1 << m) != n:
            raise ValueError("n must be of the form 2^m")

        # パリティ行列 P を生成
        p = []
        for i in range(1, n):  # 1から2^m-1まで
            # p.append([(i >> j) & 1 for j in range(m)])
            row = 0x0
            for j in range(m):
                # row.append((i >> j) & 1)
                row |= ((i >> j) & 1) << j
            p.append(row)

        # 生成行列 G を構築
        g = []
        for i in range(k):
            # row = [0] * k
            row = 0x0
            # row[i] = 1  # 単位行列部分
            row |= 1 << i
            # row.extend(p[i])  # パリティ行列部分
            for j in range(m):
                # row.append(p[i][j])
                row |= ((p[i] >> j) & 1) << (k + j)
            g.append(row)

        # 拡張パリティビットを追加 (最後の列に偶数パリティを追加)
        for row in g:
            # parity = sum(row) % 2
            bitcount = str(bin(row)).count("1")
            parity = bitcount % 2
            # row.append(parity)
            row |= parity << k

        return g


def main() -> None:
    # test_readid()
    # test_erase_program_read()
    # test_codec()

    # test_hamming_matrix()
    # 512byteごと8bitのECCをかける必要あり
    ecc = Ecc()
    n = 128
    k = 120
    matrix = ecc.gen_hamming_matrix(n, k)
    for row in matrix:
        print(f"{row:0{n}b}")


if __name__ == "__main__":
    main()
