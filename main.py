from machine import Pin
import time
import rp2

led = Pin("LED", Pin.OUT)


class NandCmd:
    READ_ID = 0x90


class NandIo:
    def __init__(self, delay_us: int = 1, is_debug: bool = True) -> None:
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

    def debug(self, msg: str) -> None:
        if self.is_debug:
            print(msg)

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
        for pin in self.io:
            pin.init(Pin.OUT if is_output else Pin.IN)

    def set_ceb(self, cs_index: int | None) -> None:
        assert cs_index is None or cs_index in [0, 1]
        if cs_index is None:
            self.ceb0.on()
            self.ceb1.on()
        else:
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
        self.set_io_dir(is_output=True)
        self.set_ceb(None)
        self.set_cle(0)
        self.set_ale(0)
        self.set_web(1)
        self.set_reb(1)

    ########################################################
    # Communication functions
    ########################################################
    def read_id(self, cs_index: int) -> bytearray:
        """ID Read Commandを実行し、IDを取得する

        Args:
            cs_index (int): CS index

        Returns:
            bytearray: ID Readの結果
        """
        id = bytearray()
        self.set_io_dir(is_output=True)
        self.set_cle(0)
        self.set_ale(0)
        self.set_web(1)
        self.set_reb(1)

        # CS select
        self.set_ceb(cs_index=cs_index)
        # Command Input
        self.set_io(NandCmd.READ_ID)
        self.set_cle(1)
        self.set_web(0)
        time.sleep_us(self.delay_us)
        self.set_web(1)
        self.set_cle(0)
        # Address Input
        self.set_io(0)
        self.set_ale(1)
        self.set_web(0)
        time.sleep_us(self.delay_us)
        self.set_web(1)
        self.set_ale(0)
        # ID Read
        self.set_io_dir(is_output=False)
        time.sleep_us(self.delay_us)
        for i in range(5):
            self.set_reb(0)
            time.sleep_us(self.delay_us)
            id.append(self.get_io())
            self.set_reb(1)
            time.sleep_us(self.delay_us)

        self.set_io_dir(is_output=True)
        # CS deselect
        self.set_ceb(None)

        return id

    def check_num_active_cs(
        self,
        # for JISC-SSD TC58NVG0S3HTA00
        expect_id: bytearray = bytearray([0x98, 0xF1, 0x80, 0x15, 0x72]),
    ) -> int:
        nand = NandIo()
        nand.init_pin()
        num_cs = 0
        for cs_index in range(2):
            id = nand.read_id(cs_index=cs_index)
            is_ok = id == expect_id
            self.debug(f"[CS{cs_index}]: ID:{id.hex()} {'OK' if is_ok else 'NG'}")
            if not is_ok:
                return num_cs
            num_cs += 1


def main() -> None:
    # for JISC-SSD TC58NVG0S3HTA00
    EXPECT_ID: bytearray = bytearray([0x98, 0xF1, 0x80, 0x15, 0x72])
    nand = NandIo()
    nand.init_pin()
    num_cs = nand.check_num_active_cs(expect_id=EXPECT_ID)
    print(f"Number of active CS: {num_cs}")
    if num_cs == 0:
        print("No NAND flash is found.")
        while True:
            led.off()
            time.sleep(0.5)
            led.on()
            time.sleep(0.5)

    led.on()
    time.sleep(1)


if __name__ == "__main__":
    main()
