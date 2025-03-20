import sys
import json
import time


############################################################################
# Logging
############################################################################


# ログ制御用
class LogLevel:
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3
    TRACE = 4

    @classmethod
    def to_str(cls, level: int) -> str:
        if level == cls.ERROR:
            return "ERROR"
        elif level == cls.WARN:
            return "WARN"
        elif level == cls.INFO:
            return "INFO"
        elif level == cls.DEBUG:
            return "DEBUG"
        elif level == cls.TRACE:
            return "TRACE"
        else:
            return "UNKNOWN"


# ログレベルの設定 (default)
CURRENT_LOG_LEVEL = LogLevel.TRACE


def log(level: int, msg: str) -> None:
    if level <= CURRENT_LOG_LEVEL:
        print(f"[{LogLevel.to_str(level)}]{msg}")
    else:
        pass


def error(msg: str) -> None:
    log(LogLevel.ERROR, msg)


def warn(msg: str) -> None:
    log(LogLevel.WARN, msg)


def info(msg: str) -> None:
    log(LogLevel.INFO, msg)


def debug(msg: str) -> None:
    log(LogLevel.DEBUG, msg)


def trace(msg: str) -> None:
    log(LogLevel.TRACE, msg)


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


############################################################################
# NAND Flash I/O
############################################################################

if sys.platform == "linux":
    # micropython on WSL or Linux
    # ABC classやdataclassなどを使いたいところだが、micropythonなのでifdef相当で振る舞い差し替え
    # TODO:
    pass
else:
    # 現時点ではJISC-SSD (rp2040) のみを想定
    from machine import Pin
    import rp2

    class NandIo:
        def __init__(
            self,
            delay_us: int = 0,
        ) -> None:
            self._delay_us = delay_us
            self._io0 = Pin(0, Pin.OUT)
            self._io1 = Pin(1, Pin.OUT)
            self._io2 = Pin(2, Pin.OUT)
            self._io3 = Pin(3, Pin.OUT)
            self._io4 = Pin(4, Pin.OUT)
            self._io5 = Pin(5, Pin.OUT)
            self._io6 = Pin(6, Pin.OUT)
            self._io7 = Pin(7, Pin.OUT)
            self._ceb0 = Pin(8, Pin.OUT)
            self._ceb1 = Pin(9, Pin.OUT)
            self._cle = Pin(10, Pin.OUT)
            self._ale = Pin(11, Pin.OUT)
            self._wpb = Pin(12, Pin.OUT)
            self._web = Pin(13, Pin.OUT)
            self._reb = Pin(14, Pin.OUT)
            self._rbb = Pin(15, Pin.IN, Pin.PULL_UP)

            self._io = [
                self._io0,
                self._io1,
                self._io2,
                self._io3,
                self._io4,
                self._io5,
                self._io6,
                self._io7,
            ]
            self._ceb = [self._ceb0, self._ceb1]
            # debug indicator
            self._led = Pin("LED", Pin.OUT, value=1)

            self.setup_pin()

        def seq_delay(self) -> None:
            time.sleep_us(self._delay_us)

        ########################################################
        # Low-level functions
        ########################################################

        def set_io(self, value: int) -> None:
            for i in range(8):
                self._io[i].value((value >> i) & 0x1)

        def get_io(self) -> int:
            value = 0
            for i in range(8):
                value |= self._io[i].value() << i
            return value

        def set_io_dir(self, is_output: bool) -> None:
            trace(f"IO\tIO\t{'OUT' if is_output else 'IN'}")
            for pin in self._io:
                pin.init(Pin.OUT if is_output else Pin.IN)

        def set_ceb(self, cs_index: int | None) -> None:
            # status indicator
            self._led.toggle()

            assert cs_index is None or cs_index in [0, 1]
            if cs_index is None:
                trace("CS\tNone")
                self._ceb0.on()
                self._ceb1.on()
            else:
                trace(f"IO\tCS\t{cs_index}")
                self._ceb0.value(0 if cs_index == 0 else 1)
                self._ceb1.value(0 if cs_index == 1 else 1)

        def set_cle(self, value: int) -> None:
            self._cle.value(value)

        def set_ale(self, value: int) -> None:
            self._ale.value(value)

        def set_web(self, value: int) -> None:
            self._web.value(value)

        def set_wpb(self, value: int) -> None:
            self._wpb.value(value)
            trace(f"IO\tWPB\t{value}")
            time.sleep_us(100)

        def set_reb(self, value: int) -> None:
            self._reb.value(value)

        def setup_pin(self) -> None:
            trace("IO\tSETUP")
            for pin in self._io:
                pin.init(Pin.OUT)
                pin.off()
            for pin in self._ceb:
                pin.init(Pin.OUT)
                pin.on()
            self._cle.init(Pin.OUT)
            self._cle.off()
            self._ale.init(Pin.OUT)
            self._ale.off()
            self._wpb.init(Pin.OUT)
            self._wpb.on()
            self._web.init(Pin.OUT)
            self._web.on()
            self._reb.init(Pin.OUT)
            self._reb.on()
            self._rbb.init(Pin.IN, Pin.PULL_UP)

        def get_rbb(self) -> int:
            return self._rbb.value()

        def init_pin(self) -> None:
            trace("IO\tINIT")
            self.set_io_dir(is_output=True)
            self.set_ceb(None)
            self.set_cle(0)
            self.set_ale(0)
            self.set_web(1)
            self.set_reb(1)

        def input_cmd(self, cmd: int) -> None:
            trace(f"IO\tCMD\t{cmd:02X}")
            self.set_io(cmd)
            self.set_cle(1)
            self.set_web(0)
            self.seq_delay()
            self.set_web(1)
            self.set_cle(0)

        def input_addrs(self, addrs: bytearray) -> None:
            trace(f"IO\tADDR\t{addrs.hex()}")
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
            trace(f"IO\tDOUT\t{datas.hex()}")
            self.set_io_dir(is_output=True)
            return datas

        def wait_busy(self, timeout_ms: int) -> bool:
            start = time.ticks_ms()
            while self.get_rbb() == 0:
                if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                    return False
            return True

    class NandCommander:
        def __init__(
            self,
            nandio: NandIo,
            timeout_ms: int = 1000,
        ) -> None:
            self._timeout_ms = timeout_ms
            self._nandio = nandio

        ########################################################
        # Communication functions
        ########################################################
        def read_id(self, cs_index: int, num_bytes: int = 5) -> bytearray:
            nandio = self._nandio

            # initialize
            nandio.init_pin()
            # CS select
            nandio.set_ceb(cs_index=cs_index)
            # Command Input
            nandio.input_cmd(NandCmd.READ_ID)
            # Address Input
            nandio.input_addr(0)
            # ID Read
            id = nandio.output_data(num_bytes=num_bytes)
            # CS deselect
            nandio.set_ceb(None)

            trace(f"CMD\t{self.read_id.__name__}\tcs={cs_index}\tid={id.hex()}")

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
            nand = self._nandio
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
            is_ok = nand.wait_busy(timeout_ms=self._timeout_ms)
            if not is_ok:
                trace(f"CMD\t{self.read_page.__name__}\ttimeout")
                return None
            # Data Read
            data = nand.output_data(num_bytes=num_bytes)
            # CS deassert
            nand.set_ceb(None)
            return data

        def read_status(self, cs_index: int) -> int:
            nand = self._nandio
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
            nand = self._nandio
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
            is_ok = nand.wait_busy(timeout_ms=self._timeout_ms)
            if not is_ok:
                trace(f"CMD\t{self.erase_block.__name__}\ttimeout")
                return False
            # CS deassert
            nand.set_ceb(None)

            # status read (erase result)
            status = self.read_status(cs_index=cs_index)
            is_ok = (status & NandStatus.PROGRAM_ERASE_FAIL) == 0

            trace(
                f"CMD\t{self.erase_block.__name__}\tcs={cs_index}\tblock={block}\tis_ok={is_ok}\tstatus={status:02X}"
            )
            return is_ok

        def program_page(
            self,
            cs_index: int,
            block: int,
            page: int,
            data: bytearray,
            col: int = 0,
        ) -> bool:
            page_addr = NandConfig.create_nand_addr(block=block, page=page, col=col)
            nand = self._nandio
            # initialize
            nand.init_pin()
            # CS select
            nand.set_ceb(cs_index=cs_index)
            # 1st Command Input
            nand.input_cmd(NandCmd.PROGRAM_1ST)
            # Address Input
            nand.input_addrs(page_addr)
            # Data Input
            for i in range(len(data)):
                nand.set_io(data[i])
                nand.set_web(0)
                nand.seq_delay()
                nand.set_web(1)
            # 2nd Command Input
            nand.input_cmd(NandCmd.PROGRAM_2ND)
            # Wait Busy
            is_ok = nand.wait_busy(timeout_ms=self._timeout_ms)
            if not is_ok:
                trace(f"CMD\t{self.program_page.__name__}\ttimeout")
                return False
            # CS deassert
            nand.set_ceb(None)

            # status read (program result)
            status = self.read_status(cs_index=cs_index)
            is_ok = (status & NandStatus.PROGRAM_ERASE_FAIL) == 0

            trace(
                f"CMD\t{self.program_page.__name__}\tcs={cs_index}\tblock={block}\tpage={page}\tis_ok={is_ok}\tstatus={status:02X}"
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
                trace(
                    f"CMD\t{self.check_num_active_cs.__name__}\tcs={cs_index}\tis_ok={is_ok}"
                )
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
                    trace(
                        f"CMD\t{self.check_badblocks.__name__}\tcs={cs_index}\tblock={block}\tException"
                    )
                    return None
                # Check Bad Block
                is_bad = data[0] != 0xFF
                if is_bad:
                    badblock_bitmap |= 1 << block
                trace(
                    f"CMD\t{self.check_badblocks.__name__}\tcs={cs_index}\tblock={block}\tis_bad={is_bad}"
                )
            return badblock_bitmap


class NandBlockManager:
    def __init__(
        self,
        nandcmd: NandCommander,
        keep_wp: bool = True,
        # initialized values
        is_initial: bool = False,
        num_cs: int = 0,
        initial_badblock_bitmaps: list[int] = [],
    ) -> None:
        self._nandcmd = nandcmd
        self._nandcmd._nandio.set_wpb(0 if keep_wp else 1)

        if not is_initial:
            try:
                self.load()
                trace(f"BLKMNG\t{self.__init__.__name__}\tload")
            except OSError as e:
                trace(f"BLKMNG\t{self.__init__.__name__}\tload error={e}")
                is_initial = True

        if is_initial:
            trace(f"BLKMNG\t{self.__init__.__name__}\tinitialize")
            self.num_cs = num_cs
            self.badblock_bitmaps = initial_badblock_bitmaps
            self.init()
            # save initialized values
            self.save()

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
            trace(f"BLKMNG\t{self.save.__name__}\t{filepath}\t{json_str}")
        except OSError as e:
            raise e

    def load(self, filepath: str = "nand_block_allocator.json") -> None:
        try:
            f = open(filepath, "r")
            json_text = f.read()
            data = json.loads(json_text)
            self.num_cs = data["num_cs"]
            self.badblock_bitmaps = data["badblock_bitmaps"]
            self.allocated_bitmaps = data["allocated_bitmaps"]
            f.close()
            trace(f"BLKMNG\t{self.load.__name__}\t{filepath}\t{json_text}")
        except OSError as e:
            raise e

    ########################################################
    # Application functions
    ########################################################
    def init(self) -> None:
        # cs
        if self.num_cs == 0:
            self.num_cs = self._nandcmd.check_num_active_cs()
        if self.num_cs == 0:
            raise ValueError("No Active CS")

        trace(f"BLKMNG\t{self.init.__name__}\tnum_cs={self.num_cs}")
        # badblock
        if self.badblock_bitmaps is None:
            self.badblock_bitmaps = []
        for cs_index in range(self.num_cs):
            # 片方のCSだけ初期値未設定ケースがあるので追加してからチェックした値をセット
            if len(self.badblock_bitmaps) < cs_index:
                self.badblock_bitmaps.append(0)
                bitmaps = self._nandcmd.check_badblocks(cs_index=cs_index)
                if bitmaps is None:
                    raise ValueError("BadBlock Check Error")
                else:
                    self.badblock_bitmaps[cs_index] = bitmaps
        for cs_index in range(self.num_cs):
            trace(
                f"BLKMNG\t{self.init.__name__}\tbadblock\tcs={cs_index}\t{self.badblock_bitmaps[cs_index]:0x}"
            )
        # allocated bitmap
        self.allocated_bitmaps = [0] * self.num_cs
        # badblock部分は確保済としてマーク
        for cs_index in range(self.num_cs):
            self.allocated_bitmaps[cs_index] = self.badblock_bitmaps[cs_index]
        for cs_index in range(self.num_cs):
            trace(
                f"BLKMNG\t{self.init.__name__}\tallocated\tcs={cs_index}\t{self.allocated_bitmaps[cs_index]:0x}"
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
                # Erase Block
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


def main() -> None:
    nandio = NandIo()
    nandcmd = NandCommander(nandio=nandio)
    blockmng = NandBlockManager(
        nandcmd=nandcmd,
        keep_wp=False,
    )
    block = blockmng.alloc()
    print(f"Allocated Block: {block}")

    read_data0 = blockmng.read(cs_index=0, block=block, page=0)
    assert read_data0 is not None
    print(f"Read Data: {read_data0.hex()}")

    write_data = bytearray([x & 0xFF for x in range(NandConfig.PAGE_BYTES)])
    is_ok = blockmng.program(cs_index=0, block=block, page=0, data=write_data)
    print(f"Program Result: {is_ok}")

    read_data1 = blockmng.read(cs_index=0, block=block, page=0)
    assert read_data1 is not None
    print(f"Read Data: {read_data1.hex()}")
    print(f"Data Match: {read_data1 == write_data}")


if __name__ == "__main__":
    main()
