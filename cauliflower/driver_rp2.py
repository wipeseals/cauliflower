import time

from log import error, trace, debug, info, LogLevel
from nand import NandConfig, NandCmd, NandStatus

from machine import Pin


class NandIo:
    def __init__(
        self,
        delay_us: int = 0,
        keep_wp: bool = True,
    ) -> None:
        self._delay_us = delay_us
        self._keep_wp = keep_wp
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

    def delay(self) -> None:
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
        if self._keep_wp:
            self.set_wpb(0)
            info("IO\tWPB\tWrite Protect Enable")
        else:
            self.set_wpb(1)
            info("IO\tWPB\tWrite Protect Disable")
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
        self.delay()
        self.set_web(1)
        self.set_cle(0)

    def input_addrs(self, addrs: bytearray) -> None:
        trace(f"IO\tADDR\t{addrs.hex()}")
        for addr in addrs:
            self.set_io(addr)
            self.set_ale(1)
            self.set_web(0)
            self.delay()
            self.set_web(1)
            self.set_ale(0)

    def input_addr(self, addr: int) -> None:
        self.input_addrs(bytearray([addr]))

    def output_data(self, num_bytes: int) -> bytearray:
        datas = bytearray()
        self.set_io_dir(is_output=False)
        for i in range(num_bytes):
            self.set_reb(0)
            self.delay()
            datas.append(self.get_io())
            self.set_reb(1)
            self.delay()
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
        num_bytes: int = NandConfig.PAGE_ALL_BYTES,
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
            nand.delay()
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
