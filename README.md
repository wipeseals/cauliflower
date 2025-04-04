# Cauliflower

Toy USB Massstorage device running on raspberry pi pico implemented in MicroPython.

## Features

TODO:

## Getting Started

### RPi Pico ([JISC-SSD](https://crane-elec.co.jp/products/vol-28/)) 上で実行する

- MicroPython のインストール
  - Raspberry Pi Pico の公式サイトから、RP2040 用の MicroPython Runtime の UF2 File をダウンロードし書き込み
    - 詳細は [MicroPython - Raspberry Pi](https://www.raspberrypi.com/documentation/microcontrollers/micropython.html) を参照。
- Cauliflower を実行
  - Cauliflower のリポジトリをクローン
  - `src` の内容を Raspberry Pi Pico 上に転送して実行
    - vscode + [MicroPico Extension](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go): `MicroPico: Upload project to Pico`
    - mpremote: `mpremote run main.py`

```bash
[DEBUG]Use RP2040 Driver
[TRACE]IO       SETUP
[TRACE]IO       WPB     1
[INFO]IO        WPB     Write Protect Disable
[TRACE]BLKMNG   load    nand_block_allocator.json       {"num_cs": 1, "allocated_bitma ...
```

### Linux/Windows 上で実行する

MicroPython の Windows/Linux 向けポートを用いれば、そのまま実行することができます。
NAND Flash への Read/Erase/Program 操作は、 `nand_datas/*.bin` のファイル操作に置き換えられます。

```bash
$ micropython -i src/main.py
[DEBUG]Use Linux Driver
[ERROR]Failed to create directory: nand_datas
[TRACE]BLKMNG   load    nand_block_allocator.json       {"num_cs": 1, "badblock_bitmaps": [0], "allocated_bitmaps": [0]}
[TRACE]BLKMNG   __init__        load
[TRACE]CMD      erase_block     cs=0    block=0 is_ok=True
[TRACE]BLKMNG   _mark_alloc     cs=0    block=0 1
...
```

### Nix 環境/NixOs 上で実行

nix, flakes, direnv を利用している場合、以下のコマンドで実行することができます。

```bash
$ direnv allow # 初回のみ
direnv: loading /mnt/e/repos/cauliflower/.envrc
direnv: using flake
direnv: nix-direnv: Using cached dev shell
direnv: export +CONFIG_SHELL +DETERMINISTIC_BUILD +HOST_PAT...

$ micropython -i src/main.py
[DEBUG]Use Linux Driver
[ERROR]Failed to create directory: nand_datas
[TRACE]BLKMNG   load    nand_block_allocator.json       {"num_cs": 1, "badblock_bitmaps": [0], "allocated_bitmaps": [0]}
[TRACE]BLKMNG   __init__        load
[TRACE]CMD      erase_block     cs=0    block=0 is_ok=True
[TRACE]BLKMNG   _mark_alloc     cs=0    block=0 1
...
```

### Structure

TODO:

## Reference

- [[VOL-28]JISC-SSD(Jisaku In-Storage Computation SSD 学習ボード)](https://crane-elec.co.jp/products/vol-28/)
- [TC58NVG0S3HTA00 Datasheet](https://www.kioxia.com/content/dam/kioxia/newidr/productinfo/datasheet/201910/DST_TC58NVG0S3HTA00-TDE_EN_31435.pdf)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [GitHub - crane-elec/rawnand_test](https://github.com/crane-elec/rawnand_test)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
