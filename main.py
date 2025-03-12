from machine import Pin
import time
import rp2

led = Pin("LED", Pin.OUT)


class NandCmd:
    READ_ID = 0x90


class NandIo:
    def __init__(
        self,
        delay_us: int = 1,
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
        self.set_io_dir(is_output=True)
        self.debug(f"DOUT\t{datas.hex()}")
        return datas


class NandCommander:
    def __init__(self, nand: NandIo, is_debug: bool = True) -> None:
        self.is_debug = is_debug
        self.nand = nand

    def debug(self, msg: str) -> None:
        if self.is_debug:
            print(f"[DEBUG]\tNandCmd\t{msg}")

    ########################################################
    # Communication functions
    ########################################################
    def read_id(self, cs_index: int, num_bytes: int = 5) -> bytearray:
        """ID Read Commandを実行し、IDを取得する

        Args:
            cs_index (int): CS index

        Returns:
            bytearray: ID Readの結果
        """
        # initialize
        self.nand.init_pin()
        # CS select
        self.nand.set_ceb(cs_index=cs_index)
        # Command Input
        self.nand.input_cmd(NandCmd.READ_ID)
        # Address Input
        self.nand.input_addr(0)
        # ID Read
        id = self.nand.output_data(num_bytes=num_bytes)
        # CS deselect
        self.nand.set_ceb(None)

        self.debug(f"read_id\tcs={cs_index}\tid={id.hex()}")

        return id

    # def read_page(self, cs_index: int, addr:NandAddr) -> bytearray:
    #     addr.

    ########################################################
    # Application functions
    ########################################################
    def check_num_active_cs(
        self,
        check_num_cs: int = 2,
        # for JISC-SSD TC58NVG0S3HTA00
        expect_id: bytearray = bytearray([0x98, 0xF1, 0x80, 0x15, 0x72]),
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


def panic(cond: bool, msg: str) -> None:
    if cond:
        print(msg)
        while True:
            led.off()
            time.sleep(0.5)
            led.on()
            time.sleep(0.5)


def main() -> None:
    nandio = NandIo(is_debug=True)
    nandcmd = NandCommander(nand=nandio, is_debug=True)
    num_cs = nandcmd.check_num_active_cs()
    print(f"Number of active CS: {num_cs}")
    panic(num_cs == 0, "No NAND flash is found.")


if __name__ == "__main__":
    main()
