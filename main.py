import os
import json
from machine import Pin
import time
import rp2

led = Pin("LED", Pin.OUT)


def panic(cond: bool, msg: str) -> None:
    if cond:
        print(msg)
        while True:
            led.off()
            time.sleep(0.5)
            led.on()
            time.sleep(0.5)


class NandCmd:
    READ_ID = 0x90
    READ_1ST = 0x00
    READ_2ND = 0x30
    ERASE_1ST = 0x60
    ERASE_2ND = 0xD0
    STATUS_READ = 0x70


class NandStatus:
    PROGRAM_ERASE_FAIL = 0x01
    CACHE_PROGRAM_FAIL = 0x02
    PAGE_BUFFER_READY = 0x20
    DATA_CACHE_READY = 0x40
    WRITE_PROTECT_DISABLE = 0x80


class NandIo:
    def __init__(
        self,
        delay_us: int = 0,
        is_debug: bool = True,
    ) -> None:
        self.is_debug = is_debug
        self.delay_us = delay_us
        self.io0 = Pin(0, Pin.OUT)
        self.io1 = Pin(1, Pin.OUT)
        self.io2 = Pin(2, Pin.OUT)
        self.io3 = Pin(3, Pin.OUT)
        self.io4 = Pin(4, Pin.OUT)
        self.io5 = Pin(5, Pin.OUT)
        self.io6 = Pin(6, Pin.OUT)
        self.io7 = Pin(7, Pin.OUT)
        self.ceb0 = Pin(8, Pin.OUT)
        self.ceb1 = Pin(9, Pin.OUT)
        self.cle = Pin(10, Pin.OUT)
        self.ale = Pin(11, Pin.OUT)
        self.wpb = Pin(12, Pin.OUT)
        self.web = Pin(13, Pin.OUT)
        self.reb = Pin(14, Pin.OUT)
        self.rbb = Pin(15, Pin.IN, Pin.PULL_UP)

        self.io = [
            self.io0,
            self.io1,
            self.io2,
            self.io3,
            self.io4,
            self.io5,
            self.io6,
            self.io7,
        ]
        self.ceb = [self.ceb0, self.ceb1]
        self.setup_pin()

    def seq_delay(self) -> None:
        time.sleep_us(self.delay_us)

    def debug(self, msg: str) -> None:
        if self.is_debug:
            print(f"[DEBUG]\tNandIo\t{msg}")

    ########################################################
    # Low-level functions
    ########################################################

    def set_io(self, value: int) -> None:
        for i in range(8):
            self.io[i].value((value >> i) & 0x1)

    def get_io(self) -> int:
        value = 0
        for i in range(8):
            value |= self.io[i].value() << i
        return value

    def set_io_dir(self, is_output: bool) -> None:
        self.debug(f"IO\t{'OUT' if is_output else 'IN'}")
        for pin in self.io:
            pin.init(Pin.OUT if is_output else Pin.IN)

    def set_ceb(self, cs_index: int | None) -> None:
        assert cs_index is None or cs_index in [0, 1]
        if cs_index is None:
            self.debug("CS\tNone")
            self.ceb0.on()
            self.ceb1.on()
        else:
            self.debug(f"CS\t{cs_index}")
            self.ceb0.value(0 if cs_index == 0 else 1)
            self.ceb1.value(0 if cs_index == 1 else 1)

    def set_cle(self, value: int) -> None:
        self.cle.value(value)

    def set_ale(self, value: int) -> None:
        self.ale.value(value)

    def set_web(self, value: int) -> None:
        self.web.value(value)

    def set_wpb(self, value: int) -> None:
        self.wpb.value(value)
        self.debug(f"WPB\t{value}")
        time.sleep_us(100)

    def set_reb(self, value: int) -> None:
        self.reb.value(value)

    def setup_pin(self) -> None:
        self.debug("SETUP")
        for pin in self.io:
            pin.init(Pin.OUT)
            pin.off()
        for pin in self.ceb:
            pin.init(Pin.OUT)
            pin.on()
        self.cle.init(Pin.OUT)
        self.cle.off()
        self.ale.init(Pin.OUT)
        self.ale.off()
        self.wpb.init(Pin.OUT)
        self.wpb.on()
        self.web.init(Pin.OUT)
        self.web.on()
        self.reb.init(Pin.OUT)
        self.reb.on()
        self.rbb.init(Pin.IN, Pin.PULL_UP)

    def get_rbb(self) -> int:
        return self.rbb.value()

    def init_pin(self) -> None:
        self.debug("INIT")
        self.set_io_dir(is_output=True)
        self.set_ceb(None)
        self.set_cle(0)
        self.set_ale(0)
        self.set_web(1)
        self.set_reb(1)

    def input_cmd(self, cmd: int) -> None:
        self.debug(f"CMD\t{cmd:02X}")
        self.set_io(cmd)
        self.set_cle(1)
        self.set_web(0)
        self.seq_delay()
        self.set_web(1)
        self.set_cle(0)

    def input_addrs(self, addrs: bytearray) -> None:
        self.debug(f"ADDR\t{addrs.hex()}")
        for addr in addrs:
            self.set_io(addr)
            self.set_ale(1)
            self.set_web(0)
            self.seq_delay()
            self.set_web(1)
            self.set_ale(0)

    def input_addr(self, addr: int) -> None:
        self.input_addrs(bytearray([addr]))

    def output_data(self, num_bytes: int) -> bytearray:
        datas = bytearray()
        self.set_io_dir(is_output=False)
        for i in range(num_bytes):
            self.set_reb(0)
            self.seq_delay()
            datas.append(self.get_io())
            self.set_reb(1)
            self.seq_delay()
        self.debug(f"DOUT\t{datas.hex()}")
        self.set_io_dir(is_output=True)
        return datas

    def wait_busy(self, timeout_ms: int) -> bool:
        start = time.ticks_ms()
        while self.get_rbb() == 0:
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                return False
        return True


class NandConfig:
    """
    NAND Flash Configuration for JISC-SSD TC58NVG0S3HTA00
    note: 動作中に別NANDに切り替えることはないのでinstanceを巻いたりしない
    """

    # JISC-SSD TC58NVG0S3HTA00 x 2
    MAX_CS = 2
    # ID Read Command for TC58NVG0S3HTA00
    READ_ID_EXPECT = bytearray([0x98, 0xF1, 0x80, 0x15, 0x72])
    # 2048byte(main) + 128byte(redundancy or other uses)
    PAGE_BYTES = 2048 + 128
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


class NandCommander:
    def __init__(
        self,
        nand: NandIo,
        timeout_ms: int = 1000,
        is_debug: bool = True,
    ) -> None:
        self.is_debug = is_debug
        self.timeout_ms = timeout_ms
        self.nand = nand

    def debug(self, msg: str) -> None:
        if self.is_debug:
            print(f"[DEBUG]\tNandCmd\t{msg}")

    ########################################################
    # Communication functions
    ########################################################
    def read_id(self, cs_index: int, num_bytes: int = 5) -> bytearray:
        nand = self.nand

        # initialize
        nand.init_pin()
        # CS select
        nand.set_ceb(cs_index=cs_index)
        # Command Input
        nand.input_cmd(NandCmd.READ_ID)
        # Address Input
        nand.input_addr(0)
        # ID Read
        id = nand.output_data(num_bytes=num_bytes)
        # CS deselect
        nand.set_ceb(None)

        self.debug(f"read_id\tcs={cs_index}\tid={id.hex()}")

        return id

    def read_page(
        self,
        cs_index: int,
        block: int,
        page: int,
        col: int = 0,
        num_bytes: int = NandConfig.PAGE_BYTES,
    ) -> bytearray | None:
        page_addr = NandConfig.create_nand_addr(block=block, page=page, col=col)
        nand = self.nand
        # initialize
        nand.init_pin()
        # CS select
        nand.set_ceb(cs_index=cs_index)
        # 1st Command Input
        nand.input_cmd(NandCmd.READ_1ST)
        # Address Input
        nand.input_addrs(page_addr)
        # 2nd Command Input
        nand.input_cmd(NandCmd.READ_2ND)
        # Wait Busy
        is_ok = nand.wait_busy(timeout_ms=self.timeout_ms)
        if not is_ok:
            self.debug("read_page\ttimeout")
            return None
        # Data Read
        data = nand.output_data(num_bytes=num_bytes)
        # CS deassert
        nand.set_ceb(None)
        return data

    def read_status(self, cs_index: int) -> int:
        nand = self.nand
        # initialize
        nand.init_pin()
        # CS select
        nand.set_ceb(cs_index=cs_index)
        # Command Input
        nand.input_cmd(NandCmd.STATUS_READ)
        # Status Read
        status = nand.output_data(num_bytes=1)
        # CS deselect
        nand.set_ceb(None)
        return status[0]

    def erase_block(self, cs_index: int, block: int) -> bool:
        block_addr = NandConfig.create_block_addr(block=block)
        nand = self.nand
        # initialize
        nand.init_pin()
        # CS select
        nand.set_ceb(cs_index=cs_index)
        # 1st Command Input
        nand.input_cmd(NandCmd.ERASE_1ST)
        # Address Input
        nand.input_addrs(block_addr)
        # 2nd Command Input
        nand.input_cmd(NandCmd.ERASE_2ND)
        # Wait Busy
        is_ok = nand.wait_busy(timeout_ms=self.timeout_ms)
        if not is_ok:
            self.debug("erase_block\ttimeout")
            return False
        # CS deassert
        nand.set_ceb(None)

        # status read (erase result)
        status = self.read_status(cs_index=cs_index)
        is_ok = (status & NandStatus.PROGRAM_ERASE_FAIL) == 0

        self.debug(
            f"erase_block\tcs={cs_index}\tblock={block}\tis_ok={is_ok}\tstatus={status:02X}"
        )
        return is_ok

    ########################################################
    # Application functions
    ########################################################
    def check_num_active_cs(
        self,
        check_num_cs: int = 2,
        expect_id: bytearray = NandConfig.READ_ID_EXPECT,
    ) -> int:
        num_cs = 0
        for cs_index in range(check_num_cs):
            id = self.read_id(cs_index=cs_index)
            is_ok = id == expect_id
            self.debug(f"check_num_active_cs\tcs={cs_index}\tis_ok={is_ok}")
            if not is_ok:
                return num_cs
            num_cs += 1
        return num_cs

    def check_badblocks(
        self, cs_index: int, num_blocks: int = NandConfig.BLOCKS_PER_CS
    ) -> int | None:
        badblock_bitmap = 0
        for block in range(num_blocks):
            data = self.read_page(
                cs_index=cs_index, block=block, page=0, col=0, num_bytes=1
            )
            # Read Exception
            if data is None:
                self.debug(f"check_badblocks\tcs={cs_index}\tblock={block}\tException")
                return None
            # Check Bad Block
            is_bad = data[0] != 0xFF
            if is_bad:
                badblock_bitmap |= 1 << block
            self.debug(
                f"check_badblocks\tcs={cs_index}\tblock={block}\tis_bad={is_bad}"
            )
        return badblock_bitmap


class NandBlockAllocator:
    def __init__(
        self,
        nandcmd: NandCommander,
        is_debug: bool = True,
        keep_wp: bool = True,
        # initialized values
        is_initial: bool = False,
        num_cs: int = 0,
        initial_badblock_bitmaps: list[int] = [],
    ) -> None:
        self.nandcmd = nandcmd
        self.is_debug = is_debug

        if not keep_wp:
            self.nandcmd.nand.set_wpb(0)

        if not is_initial:
            try:
                self.load()
            except OSError as e:
                self.debug(f"load\terror={e}")
                is_initial = True

        if is_initial:
            self.debug("initialize")
            self.num_cs = num_cs
            self.badblock_bitmaps = initial_badblock_bitmaps
            self.init()
            # save initialized values
            self.save()

    def debug(self, msg: str) -> None:
        if self.is_debug:
            print(f"[DEBUG]\tFTL\t{msg}")

    def save(self, filepath: str = "nand_block_allocator.json") -> None:
        json_str = json.dumps(
            {
                "num_cs": self.num_cs,
                "badblock_bitmaps": self.badblock_bitmaps,
                "allocated_bitmaps": self.allocated_bitmaps,
            }
        )
        try:
            f = open(filepath, "w")
            f.write(json_str)
            f.close()
            self.debug(f"save\t{filepath}")
        except OSError as e:
            raise e

    def load(self, filepath: str = "nand_block_allocator.json") -> None:
        try:
            f = open(filepath, "r")
            data = json.loads(f.read())
            self.num_cs = data["num_cs"]
            self.badblock_bitmaps = data["badblock_bitmaps"]
            self.allocated_bitmaps = data["allocated_bitmaps"]
            f.close()
            self.debug(f"load\t{filepath}")
        except OSError as e:
            raise e

    ########################################################
    # Application functions
    ########################################################
    def init(self) -> None:
        # cs
        if self.num_cs == 0:
            self.num_cs = self.nandcmd.check_num_active_cs()
        panic(self.num_cs == 0, "No NAND Flash Found")
        self.debug(f"init\tnum_cs={self.num_cs}")
        # badblock
        if self.badblock_bitmaps is None:
            self.badblock_bitmaps = []
        for cs_index in range(self.num_cs):
            # 片方のCSだけ初期値未設定ケースがあるので追加してからチェックした値をセット
            if len(self.badblock_bitmaps) < cs_index:
                self.badblock_bitmaps.append(0)
                bitmaps = self.nandcmd.check_badblocks(cs_index=cs_index)
                if bitmaps is None:
                    panic(True, "Bad Block Check Failed")
                else:
                    self.badblock_bitmaps[cs_index] = bitmaps
        for cs_index in range(self.num_cs):
            self.debug(
                f"init\tbadblock\tcs={cs_index}\t{self.badblock_bitmaps[cs_index]:0x}"
            )
        # allocated bitmap
        self.allocated_bitmaps = [0] * self.num_cs
        # badblock部分は確保済としてマーク
        for cs_index in range(self.num_cs):
            self.allocated_bitmaps[cs_index] = self.badblock_bitmaps[cs_index]
        for cs_index in range(self.num_cs):
            self.debug(
                f"init\tallocated\tcs={cs_index}\t{self.allocated_bitmaps[cs_index]:0x}"
            )

    def _pick_free(self) -> tuple[int | None, int | None]:
        # 先頭から空きを探す
        for cs_index in range(self.num_cs):
            for block in range(NandConfig.BLOCKS_PER_CS):
                # free & not badblock
                if (self.allocated_bitmaps[cs_index] & (1 << block)) == 0 and (
                    self.badblock_bitmaps[cs_index] & (1 << block)
                ) == 0:
                    return cs_index, block
        return None, None

    def _mark_alloc(self, cs_index: int, block: int) -> None:
        panic(
            (self.allocated_bitmaps[cs_index] & (1 << block)) != 0,
            "Block Already Allocated",
        )

        self.allocated_bitmaps[cs_index] |= 1 << block
        self.debug(
            f"allocate_block\tcs={cs_index}\tblock={block}\t{self.allocated_bitmaps[cs_index]:0x}"
        )

    def _mark_free(self, cs_index: int, block: int) -> None:
        panic(
            (self.allocated_bitmaps[cs_index] & (1 << block)) == 0,
            "Block Already Free",
        )

        self.allocated_bitmaps[cs_index] &= ~(1 << block)
        self.debug(
            f"free_block\tcs={cs_index}\tblock={block}\t{self.allocated_bitmaps[cs_index]:0x}"
        )

    def _mark_bad(self, cs_index: int, block: int) -> None:
        self.badblock_bitmaps[cs_index] |= 1 << block
        self.debug(
            f"mark_badblock\tcs={cs_index}\tblock={block}\t{self.badblock_bitmaps[cs_index]:0x}"
        )

    def alloc_block(self) -> int:
        while True:
            cs, block = self._pick_free()
            if block is None or cs is None:
                # 空きBlockなし、GC必要
                panic(True, "No Free Block. TODO: impl GC")
            else:
                # Erase Block
                is_erase_ok = self.nandcmd.erase_block(cs_index=cs, block=block)
                if is_erase_ok:
                    self._mark_alloc(cs_index=cs, block=block)
                    self.debug(f"alloc_block\tcs={cs}\tblock={block}")
                    return block
                else:
                    # Erase失敗、BadBlockとしてマークし、Freeせず次のBlockを探す
                    self._mark_bad(cs_index=cs, block=block)
                    self.debug(f"alloc_block\tcs={cs}\tblock={block}\tErase Failed")


def main() -> None:
    nandio = NandIo(is_debug=True)
    nandcmd = NandCommander(nand=nandio, is_debug=True)
    block_allocator = NandBlockAllocator(
        nandcmd=nandcmd,
        is_debug=True,
        keep_wp=False,
    )
    block = block_allocator.alloc_block()
    print(f"Allocated Block: {block}")

    led.on()


if __name__ == "__main__":
    main()
