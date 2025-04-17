from log import error, warn, trace, debug, info, LogLevel
from nand import NandConfig, NandBlockManager, PageCodec, get_driver

# Logical Block Address
LBA = int
# Physical Block Address
PBA = int


class Mapping:
    """LBAとPBAのマッピングを管理するクラス"""

    def __init__(self) -> None:
        self.l2p: dict[LBA, PBA] = dict()

    def resolve_l2p(self, lba: LBA) -> PBA | None:
        """LBA -> PBAの変換"""
        return self.l2p.get(lba)

    def update_l2p(self, lba: LBA, pba: PBA) -> None:
        """LBA -> PBAの割当更新"""
        self.l2p[lba] = pba


class FlashTranslationLayer:
    """Flash Translation Layer (FTL)"""

    def __init__(self) -> None:
        # NAND Drivers
        self.nandio, self.nandcmd = get_driver(keep_wp=False)
        # NAND Block Manager
        self.blockmng = NandBlockManager(nandcmd=self.nandcmd)
        # NAND Page Codec
        self.codec = PageCodec()
        # LBA -> PBAのマッピング
        self.mapping = Mapping()
        pass

    ########################################################
    # Physical Address Functions
    ########################################################

    def read_page(self, cs_index: int, block: int, page: int) -> bytearray | None:
        """指定されたページをすべて読み出し"""
        # データを読み込む
        page_data = self.blockmng.read(cs_index, block, page)
        if page_data is None:
            debug(f"Read CS{cs_index} Block{block} Page{page} failed")
            return None
        # データをデコード
        decode_page_data = self.codec.decode(page_data)
        if decode_page_data is None:
            debug(f"Decode CS{cs_index} Block{block} Page{page} failed")
            return None
        return decode_page_data

    def write_page(self, cs_index: int, block: int, page: int, data: bytearray) -> bool:
        """指定されたページを書き込む"""
        # データをエンコード
        encode_page_data = self.codec.encode(data)
        if encode_page_data is None:
            debug(f"Encode CS{cs_index} Block{block} Page{page} failed")
            return False
        # データを書き込む
        result = self.blockmng.program(cs_index, block, page, encode_page_data)
        if not result:
            debug(f"Write CS{cs_index} Block{block} Page{page} failed")
            return False
        return True

    ########################################################
    # Logical Address Functions
    ########################################################

    def read_logical(self, lba: LBA) -> bytearray | None:
        """指定されたLBAを読み出し"""
        # LBA -> PBAの変換
        pba = self.mapping.resolve_l2p(lba)
        if pba is None:
            debug(f"Read LBA {lba} failed: PBA not found")
            return None
        # PBAから Chip, Block, Page, Sectorを取得
        cs_index, block, page, sector = NandConfig.decode_phys_addr(pba)
        # データを読み込む
        page_data = self.read_page(cs_index, block, page)
        if page_data is None:
            debug(f"Read LBA {lba} failed: Page read failed")
            return None
        # ほしいSectorを取得
        sector_data = page_data[
            sector * NandConfig.SECTOR_BYTES : (sector + 1) * NandConfig.SECTOR_BYTES
        ]
        return sector_data


def main() -> None:
    ftl = FlashTranslationLayer()
    test_data = bytearray([0xFF] * NandConfig.PAGE_USABLE_BYTES)
    ftl.write_page(0, 1, 0, test_data)
    read_data = ftl.read_page(0, 1, 0)
    assert test_data == read_data, "Read data does not match written data"


if __name__ == "__main__":
    main()
