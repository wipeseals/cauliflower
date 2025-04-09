from log import error, warn, trace, debug, info, LogLevel
from nand import NandConfig, NandBlockManager, PageCodec, get_driver


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
    def __init__(self, n: int, k: int) -> None:
        """
        ECCクラスの初期化
        n: 符号長 (2^m)
        k: データ長 (n - m - 1)
        """
        self.n = n
        self.k = k
        self.g = self.gen_hamming_matrix(n, k)  # 生成行列
        self.h = self.generate_parity_check_matrix()  # パリティ検査行列

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
            row = 0x0
            for j in range(m):
                row |= ((i >> j) & 1) << j
            p.append(row)

        # 生成行列 G を構築
        g = []
        for i in range(k):
            row = 0x0
            row |= 1 << i  # 単位行列部分
            for j in range(m):
                row |= ((p[i] >> j) & 1) << (k + j)  # 検査
            g.append(row)

        return g

    def generate_parity_check_matrix(self) -> list[int]:
        """
        パリティ検査行列 H を生成
        """
        h = []
        for i in range(self.n):
            row = 0x0
            for j in range(len(self.g)):
                row |= ((self.g[j] >> i) & 1) << j
            h.append(row)
        # パリティ検査行列の最後の列に偶数パリティを追加
        for row in h:
            bitcount = str(bin(row)).count("1")
            parity = bitcount % 2
            row |= parity << len(self.g)

        # パリティ検査行列の最後の行に偶数パリティを追加
        parity_row = 0x0
        for i in range(len(self.g)):
            parity_row |= ((self.g[i] >> (len(self.g) - 1)) & 1) << i
            bitcount = str(bin(parity_row)).count("1")
            parity = bitcount % 2
            parity_row |= parity << len(self.g)
        h.append(parity_row)

        return h

    def encode(self, data: int) -> int:
        """
        データを符号化
        data: 入力データ (kビット)
        """
        codeword = 0x0
        for i in range(len(self.g)):
            bit = (data >> i) & 1
            codeword ^= bit * self.g[i]
        return codeword

    def decode(self, codeword: int) -> int:
        """
        符号語を復号
        codeword: 符号語 (nビット)
        """
        syndrom = 0x0
        for i in range(len(self.h)):
            syndrom ^= (codeword >> i) & 1 * self.h[i]

        # エラー訂正
        if syndrom != 0x0:
            error_pos: int | None = None
            for i in range(len(self.h)):
                if syndrom == self.h[i]:
                    error_pos = i
                    break
            trace(f"error_pos: {error_pos}, syndrom: {syndrom:#x}")
            # エラー訂正
            if error_pos is not None:
                codeword ^= 1 << error_pos

        # データビットを抽出
        data = 0x0
        for i in range(self.k):
            data |= ((codeword >> i) & 1) << i

        return data


def main() -> None:
    # test_codec()

    # test_hamming_matrix()
    # 512byteごと8bitのECCをかける必要あり
    n = 64  # 128
    k = 57  # 120
    ecc = Ecc(n=n, k=k)
    src = 0xAA995566
    encoded = ecc.encode(src)
    decoded = ecc.decode(encoded)
    print(f"src                    : {src:0{n}b} ({src:#x})")
    print(f"encoded                : {encoded:0{n}b} ({encoded:#x})")
    print(f"decoded                : {decoded:0{n}b} ({decoded:#x})")

    # error inject test
    error_pos = 5
    encoded_with_1bit_error = encoded ^ (1 << error_pos)
    decoded_with_1bit_error = ecc.decode(encoded_with_1bit_error)
    print(
        f"encoded_with_1bit_error: {encoded_with_1bit_error:0{n}b} ({encoded_with_1bit_error:#x})"
    )
    print(
        f"decoded_with_1bit_error: {decoded_with_1bit_error:0{n}b} ({decoded_with_1bit_error:#x})"
    )


if __name__ == "__main__":
    main()
