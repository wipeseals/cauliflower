import os
from log import error, trace, debug, info, LogLevel
from nand import NandConfig


class NandIo:
    def __init__(self, keep_wp: bool = True) -> None:
        # VCD traceしたくなった場合は実装
        pass


class NandCommander:
    def __init__(
        self,
        nandio: NandIo,
        num_chip: int = 1,
        base_dir: str = "nand_datas",
    ) -> None:
        self._nandio = nandio
        self._num_chip = num_chip
        self._base_dir = base_dir

        # os.pathが無いのでとりあえず試す
        try:
            os.mkdir(base_dir)
        except OSError:
            error(f"Failed to create directory: {base_dir}")
        # stat取れないケースは失敗
        try:
            os.stat(base_dir)
        except OSError as e:
            error(f"Failed to stat directory: {base_dir} error={e}")
            raise e

    def _data_path(self, cs_index: int, block: int, page: int) -> str:
        # check range
        if cs_index >= self._num_chip:
            raise ValueError(f"Invalid CS Index: {cs_index} (support={self._num_chip})")
        if block >= NandConfig.BLOCKS_PER_CS:
            raise ValueError(f"Invalid Block: {block} (max={NandConfig.BLOCKS_PER_CS})")
        if page >= NandConfig.PAGES_PER_BLOCK:
            raise ValueError(f"Invalid Page: {page} (max={NandConfig.PAGES_PER_BLOCK})")

        return f"{self._base_dir}/cs{cs_index:02d}_block{block:04d}_page{page:02d}.bin"

    def _read_data(self, cs_index: int, block: int, page: int) -> bytearray | None:
        path = self._data_path(cs_index=cs_index, block=block, page=page)
        try:
            with open(path, "rb") as f:
                return bytearray(f.read())
        except OSError as e:
            error(f"Failed to read file: {path} error={e}")
            return bytearray([0xFF] * NandConfig.PAGE_ALL_BYTES)

    def _write_data(
        self, cs_index: int, block: int, page: int, data: bytearray
    ) -> None:
        path = self._data_path(cs_index=cs_index, block=block, page=page)
        try:
            with open(path, "wb") as f:
                f.write(data)
        except OSError as e:
            error(f"Failed to write file: {path} error={e}")

    ########################################################
    # Communication functions
    ########################################################
    def read_id(self, cs_index: int, num_bytes: int = 5) -> bytearray:
        if cs_index < self._num_chip:
            return NandConfig.READ_ID_EXPECT
        else:
            return bytearray([0x00] * num_bytes)

    def read_page(
        self,
        cs_index: int,
        block: int,
        page: int,
        col: int = 0,
        num_bytes: int = NandConfig.PAGE_ALL_BYTES,
    ) -> bytearray | None:
        data = self._read_data(cs_index=cs_index, block=block, page=page)
        return data

    def read_status(self, cs_index: int) -> int:
        return 0x00

    def erase_block(self, cs_index: int, block: int) -> bool:
        self._write_data(
            cs_index=cs_index,
            block=block,
            page=0,
            data=bytearray([0xFF] * NandConfig.PAGE_ALL_BYTES),
        )
        trace(
            f"CMD\t{self.erase_block.__name__}\tcs={cs_index}\tblock={block}\tis_ok=True"
        )
        return True

    def program_page(
        self,
        cs_index: int,
        block: int,
        page: int,
        data: bytearray,
        col: int = 0,
    ) -> bool:
        self._write_data(cs_index=cs_index, block=block, page=page, data=data)
        trace(
            f"CMD\t{self.program_page.__name__}\tcs={cs_index}\tblock={block}\tpage={page}\tis_ok=True"
        )
        return True
