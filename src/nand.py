import sys
import json
from log import error, trace, debug, info, LogLevel


############################################################################
# NAND Flash Definitions for TC58NVG0S3HTA00
############################################################################
class NandCmd:
    READ_ID = 0x90
    READ_1ST = 0x00
    READ_2ND = 0x30
    ERASE_1ST = 0x60
    ERASE_2ND = 0xD0
    STATUS_READ = 0x70
    PROGRAM_1ST = 0x80
    PROGRAM_2ND = 0x10


class NandStatus:
    PROGRAM_ERASE_FAIL = 0x01
    CACHE_PROGRAM_FAIL = 0x02
    PAGE_BUFFER_READY = 0x20
    DATA_CACHE_READY = 0x40
    WRITE_PROTECT_DISABLE = 0x80


class NandConfig:
    """
    NAND Flash Configuration for JISC-SSD TC58NVG0S3HTA00
    note: 動作中に別NANDに切り替えることはないのでinstanceを撒かない
          現時点ではJISC-SSD以外のターゲットは想定していないのでdataclassのような動的な値決めのクラスとしては機能しない
    """

    # JISC-SSD TC58NVG0S3HTA00 x 2
    MAX_CS = 2
    # ID Read Command for TC58NVG0S3HTA00
    READ_ID_EXPECT = bytearray([0x98, 0xF1, 0x80, 0x15, 0x72])
    # data area
    PAGE_USABLE_BYTES = 2048
    # spare area
    PAGE_SPARE_BYTES = 128
    # 2048byte(main) + 128byte(redundancy or other uses)
    PAGE_ALL_BYTES = PAGE_USABLE_BYTES + PAGE_SPARE_BYTES
    # number of pages per block
    PAGES_PER_BLOCK = 64
    # number of blocks per CS
    BLOCKS_PER_CS = 1024

    @staticmethod
    def create_nand_addr(block: int, page: int, col: int) -> bytearray:
        """Create NAND Flash Address

        | cycle# | Data                  |
        |--------|-----------------------|
        | 0      | COL[7:0]              |
        | 1      | COL[15:8]             |
        | 2      | BLOCK[1:0], PAGE[5:0] |
        | 3      | BLOCK[10:2]           |
        """
        addr = bytearray()
        addr.append(col & 0xFF)
        addr.append((col >> 8) & 0xFF)
        addr.append(((block & 0x3) << 6) | (page & 0x3F))
        addr.append((block >> 2) & 0xFF)
        return addr

    @staticmethod
    def create_block_addr(block: int) -> bytearray:
        """Create NAND Flash Block Address

        | cycle | Data      |
        |-------|-----------|
        | 0     | BLOCK[7:0]|
        | 1     | BLOCK[15:8]|
        """
        addr = bytearray()
        addr.append(block & 0xFF)
        addr.append((block >> 8) & 0xFF)
        return addr


############################################################################
# RP2040 Driver or Simulator
############################################################################

sim_platforms = ["linux", "windows", "webassembly", "qemu"]
if sys.platform in sim_platforms:
    # Simulator
    import driver_sim as d_sim
else:
    # RP2040 Driver
    import driver_rp2 as d_rp2


def get_driver(
    keep_wp: bool = True,
) -> tuple[d_sim.NandIo | d_rp2.NandIo, d_sim.NandCommander | d_rp2.NandCommander]:
    is_sim = sys.platform in sim_platforms
    if is_sim:
        debug("Use Simulator Driver")
        nandio = d_sim.NandIo(keep_wp=keep_wp)
        nandcmd = d_sim.NandCommander(nandio=nandio)
        return nandio, nandcmd
    else:
        debug("Use RP2040 Driver")
        nandio = d_rp2.NandIo(keep_wp=keep_wp)
        nandcmd = d_rp2.NandCommander(nandio=nandio, timeout_ms=1000)
        return nandio, nandcmd


class NandBlockManager:
    def __init__(
        self,
        nandcmd: d_sim.NandCommander | d_rp2.NandCommander,
        # initialized values
        is_initial: bool = False,
        num_chip: int = 0,
        initial_badblock_bitmaps: list[int] | None = None,
    ) -> None:
        self._nandcmd = nandcmd

        if not is_initial:
            try:
                self.load()
                trace(f"BLKMNG\t{self.__init__.__name__}\tload")
            except OSError as e:
                trace(f"BLKMNG\t{self.__init__.__name__}\tload error={e}")
                is_initial = True

        if is_initial:
            trace(f"BLKMNG\t{self.__init__.__name__}\tinitialize")
            self.num_chip = num_chip
            self.badblock_bitmaps = (
                initial_badblock_bitmaps if initial_badblock_bitmaps else []
            )
            self.init()
            # save initialized values
            self.save()

    def save(self, filepath: str = "nand_block_allocator.json") -> None:
        json_str = json.dumps(
            {
                "num_chip": self.num_chip,
                "badblock_bitmaps": self.badblock_bitmaps,
                "allocated_bitmaps": self.allocated_bitmaps,
            }
        )
        try:
            f = open(filepath, "w")
            f.write(json_str)
            f.close()
            trace(f"BLKMNG\t{self.save.__name__}\t{filepath}\t{json_str}")
        except OSError as e:
            raise e

    def load(self, filepath: str = "nand_block_allocator.json") -> None:
        try:
            f = open(filepath, "r")
            json_text = f.read()
            data = json.loads(json_text)
            self.num_chip = data["num_chip"]
            self.badblock_bitmaps = data["badblock_bitmaps"]
            self.allocated_bitmaps = data["allocated_bitmaps"]
            f.close()
            trace(f"BLKMNG\t{self.load.__name__}\t{filepath}\t{json_text}")
        except OSError as e:
            raise e

    ########################################################
    # Wrapper functions
    ########################################################
    def _check_chip_num(
        self,
        check_num_chip: int = 2,
        expect_id: bytearray = NandConfig.READ_ID_EXPECT,
    ) -> int:
        num_chip = 0
        for cs_index in range(check_num_chip):
            id = self._nandcmd.read_id(cs_index=cs_index)
            is_ok = id == expect_id
            trace(
                f"BLKMNG\t{self._check_chip_num.__name__}\tcs={cs_index}\tis_ok={is_ok}"
            )
            if not is_ok:
                return num_chip
            num_chip += 1
        return num_chip

    def _check_allbadblocks(
        self, cs_index: int, num_blocks: int = NandConfig.BLOCKS_PER_CS
    ) -> int | None:
        badblock_bitmap = 0
        for block in range(num_blocks):
            data = self._nandcmd.read_page(
                cs_index=cs_index, block=block, page=0, col=0, num_bytes=1
            )
            # Read Exception
            if data is None:
                trace(
                    f"BLKMNG\t{self._check_allbadblocks.__name__}\tcs={cs_index}\tblock={block}\tException"
                )
                return None
            # Check Bad Block
            is_bad = data[0] != 0xFF
            if is_bad:
                badblock_bitmap |= 1 << block
            trace(
                f"BLKMNG\t{self._check_allbadblocks.__name__}\tcs={cs_index}\tblock={block}\tis_bad={is_bad}"
            )
        return badblock_bitmap

    ########################################################
    # Application functions
    ########################################################
    def init(self) -> None:
        # cs
        if self.num_chip == 0:
            self.num_chip = self._check_chip_num()
        if self.num_chip == 0:
            raise ValueError("No Active CS")

        trace(f"BLKMNG\t{self.init.__name__}\tnum_chip={self.num_chip}")
        # badblock
        if self.badblock_bitmaps is None:
            self.badblock_bitmaps = []
        for cs_index in range(self.num_chip):
            # 片方のCSだけ初期値未設定ケースがあるので追加してからチェックした値をセット
            if cs_index < len(self.badblock_bitmaps):
                # 既に設定済
                pass
            else:
                self.badblock_bitmaps.append(0)
                bitmaps = self._check_allbadblocks(cs_index=cs_index)
                if bitmaps is None:
                    raise ValueError("BadBlock Check Error")
                else:
                    self.badblock_bitmaps[cs_index] = bitmaps
        for cs_index in range(self.num_chip):
            trace(
                f"BLKMNG\t{self.init.__name__}\tbadblock\tcs={cs_index}\t{self.badblock_bitmaps[cs_index]:0x}"
            )
        # allocated bitmap
        self.allocated_bitmaps = [0] * self.num_chip
        # badblock部分は確保済としてマーク
        for cs_index in range(self.num_chip):
            self.allocated_bitmaps[cs_index] = self.badblock_bitmaps[cs_index]
        for cs_index in range(self.num_chip):
            trace(
                f"BLKMNG\t{self.init.__name__}\tallocated\tcs={cs_index}\t{self.allocated_bitmaps[cs_index]:0x}"
            )

    def _pick_free(self) -> tuple[int | None, int | None]:
        # 先頭から空きを探す
        for cs_index in range(self.num_chip):
            for block in range(NandConfig.BLOCKS_PER_CS):
                # free & not badblock
                if (self.allocated_bitmaps[cs_index] & (1 << block)) == 0 and (
                    self.badblock_bitmaps[cs_index] & (1 << block)
                ) == 0:
                    return cs_index, block
        return None, None

    def _mark_alloc(self, cs_index: int, block: int) -> None:
        if (self.allocated_bitmaps[cs_index] & (1 << block)) != 0:
            raise ValueError("Block Already Allocated")

        self.allocated_bitmaps[cs_index] |= 1 << block
        trace(
            f"BLKMNG\t{self._mark_alloc.__name__}\tcs={cs_index}\tblock={block}\t{self.allocated_bitmaps[cs_index]:0x}"
        )

    def _mark_free(self, cs_index: int, block: int) -> None:
        if (self.allocated_bitmaps[cs_index] & (1 << block)) == 0:
            raise ValueError("Block Already Free")

        self.allocated_bitmaps[cs_index] &= ~(1 << block)
        trace(
            f"BLKMNG\t{self._mark_free.__name__}\tcs={cs_index}\tblock={block}\t{self.allocated_bitmaps[cs_index]:0x}"
        )

    def _mark_bad(self, cs_index: int, block: int) -> None:
        self.badblock_bitmaps[cs_index] |= 1 << block
        trace(
            f"BLKMNG\t{self._mark_bad.__name__}\tcs={cs_index}\tblock={block}\t{self.badblock_bitmaps[cs_index]:0x}"
        )

    def alloc(self) -> int:
        while True:
            cs, block = self._pick_free()
            if block is None or cs is None:
                raise ValueError("No Free Block")
            else:
                # Erase OKのものを採用。だめならやり直し
                is_erase_ok = self._nandcmd.erase_block(cs_index=cs, block=block)
                if is_erase_ok:
                    self._mark_alloc(cs_index=cs, block=block)
                    trace(f"BLKMNG\t{self.alloc.__name__}\tcs={cs}\tblock={block}")
                    return block
                else:
                    # Erase失敗、BadBlockとしてマークし、Freeせず次のBlockを探す
                    self._mark_bad(cs_index=cs, block=block)
                    trace(
                        f"BLKMNG\t{self.alloc.__name__}\tcs={cs}\tblock={block}\tErase Failed"
                    )

    def free(self, cs_index: int, block: int) -> None:
        trace(f"BLKMNG\t{self.free.__name__}\tcs={cs_index}\tblock={block}")
        self._mark_free(cs_index=cs_index, block=block)

    def read(self, cs_index: int, block: int, page: int) -> bytearray | None:
        trace(
            f"BLKMNG\t{self.read.__name__}\tcs={cs_index}\tblock={block}\tpage={page}"
        )
        return self._nandcmd.read_page(cs_index=cs_index, block=block, page=page)

    def program(self, cs_index: int, block: int, page: int, data: bytearray) -> bool:
        trace(
            f"BLKMNG\t{self.program.__name__}\tcs={cs_index}\tblock={block}\tpage={page}"
        )
        return self._nandcmd.program_page(
            cs_index=cs_index, block=block, page=page, data=data
        )


class Lfsr8:
    """Linear Feedback Shift Register"""

    def __init__(
        self,
        init_value: int = 1,
        seed: int = 0xA5,
    ) -> None:
        self._init_value = init_value
        self._current = init_value
        self._seed = seed

    def reset(self, init_value: int | None = None):
        if init_value is not None:
            self._current = init_value
        else:
            self._current = self._init_value

    def next(self) -> int:
        self._current = (
            (self._current >> 1) ^ (-(self._current & 1) & self._seed)
        ) & 0xFF
        return self._current


class PageCodec:
    """
    NAND Flash Page Encoder/Decoder
    Reference: https://github.com/wipeseals/broccoli/blob/main/misc/design-memo/data-layout.ipynb
    """

    def __init__(
        self,
        scramble_seed: int = 0xA5,
        use_scramble: bool = True,
        use_ecc: bool = True,
        use_crc: bool = True,
    ) -> None:
        self._scramble_seed = scramble_seed
        self._use_scramble = use_scramble
        self._use_ecc = use_ecc
        self._use_crc = use_crc

    def encode(self, data: bytearray) -> bytearray:
        assert len(data) == NandConfig.PAGE_USABLE_BYTES
        # TODO: scramble
        lfsr = Lfsr8(seed=self._scramble_seed)
        data = bytearray([lfsr.next() ^ x for x in data])
        # TODO: ecc
        # TODO: crc
        return data

    def decode(self, data: bytearray) -> bytearray | None:
        assert len(data) == NandConfig.PAGE_USABLE_BYTES

        # TODO: crc
        # TODO: ecc
        # TODO: descramble
        lfsr = Lfsr8(seed=self._scramble_seed)
        data = bytearray([lfsr.next() ^ x for x in data])
        # TODO: CRC Errorを解消できなかった場合、エラー応答する
        return data
