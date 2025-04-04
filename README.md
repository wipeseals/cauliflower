# Cauliflower

Toy USB Massstorage device running on raspberry pi pico implemented in MicroPython.

## Features

TODO:

## Getting Started

### RPi Pico ([JISC-SSD](https://crane-elec.co.jp/products/vol-28/)) 上で実行する

#### MicroPython のインストール

- Raspberry Pi Pico の公式サイトから、RP2040 用の MicroPython Runtime の UF2 File をダウンロードし書き込み
  - 詳細は [MicroPython - Raspberry Pi](https://www.raspberrypi.com/documentation/microcontrollers/micropython.html) を参照

#### Cauliflower を実行

- Cauliflower のリポジトリをクローン
- `src` の内容を Raspberry Pi Pico 上に転送して実行
  - vscode + [MicroPico Extension](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go): `MicroPico: Upload project to Pico`
  - mpremote

```bash
$ uvx mpremote connect <TARGET_SERIAL> + fs --recursive --force cp src/main.py src/nand.py src/log.py src/driver_rp2.py :/ + fs ls + soft-reset + run src/main.py + rep

cp src/main.py :/
cp src/nand.py :/
cp src/log.py :/
cp src/driver_rp2.py :/
ls :
        9982 driver_rp2.py
        1105 log.py
        2015 main.py
       13921 nand.py
[7122838][DEBUG]Use RP2040 Driver
[7125017][TRACE]IO      SETUP
[7126503][TRACE]IO      WPB     1
[7127216][INFO]IO       WPB     Write Protect Disable
[7128296][TRACE]IO      INIT
[7129131][TRACE]IO      IO      OUT
[7130074][TRACE]CS      None
[7131263][TRACE]IO      CS      0
[7132279][TRACE]IO      CMD     90
[7133828][TRACE]IO      ADDR    00
[7135139][TRACE]IO      IO      IN
[7137614][TRACE]IO      DOUT    98f1801572
[7138506][TRACE]IO      IO      OUT
[7139458][TRACE]CS      None
[7140645][TRACE]CMD     read_id cs=0    id=98f1801572
[7141769][INFO]CS0: bytearray(b'\x98\xf1\x80\x15r')
[7142519][TRACE]IO      INIT
[7143347][TRACE]IO      IO      OUT
[7144267][TRACE]CS      None
[7145452][TRACE]IO      CS      1
[7146416][TRACE]IO      CMD     90
[7147888][TRACE]IO      ADDR    00
[7149164][TRACE]IO      IO      IN
[7151581][TRACE]IO      DOUT    0000000000
[7152472][TRACE]IO      IO      OUT
[7153405][TRACE]CS      None
[7154580][TRACE]CMD     read_id cs=1    id=0000000000
[7155701][INFO]CS1: bytearray(b'\x00\x00\x00\x00\x00')
Connected to MicroPython at COM13
Use Ctrl-] or Ctrl-x to exit this shell
>
MicroPython v1.24.1 on 2024-11-29; Raspberry Pi Pico with RP2040
Type "help()" for more information.
```

### Linux/Windows 上で実行する

MicroPython の Windows/Linux 向けポートを用いれば、そのまま実行することができます。
NAND Flash への Read/Erase/Program 操作は、 `nand_datas/*.bin` のファイル操作に置き換えられます。

nix, flakes, direnv を利用している場合、`direnv allow` で micropython 環境を導入できます。

```bash
$ micropython -i src/main.py
[6759914348][DEBUG]Use Simulator Driver
[6759915242][ERROR]Failed to create directory: nand_datas
[6759916347][INFO]CS0: bytearray(b'\x98\xf1\x80\x15r')
[6759916400][INFO]CS1: bytearray(b'\x00\x00\x00\x00\x00')
MicroPython v1.24.1 on 1980-01-01; linux [GCC 14.2.1] version
Use Ctrl-D to exit, Ctrl-E for paste mode
>>>
```

### Structure

- Flash Driver
  - `src/driver_rp2.py`: RP2040 用の Flash Driver
  - `src/driver_sim.py`: Simulator 用の Flash Driver
- Flash Translation
  - `src/nand.py`: NAND Flash の操作を行うクラス

## Reference

- [[VOL-28]JISC-SSD(Jisaku In-Storage Computation SSD 学習ボード)](https://crane-elec.co.jp/products/vol-28/)
- [TC58NVG0S3HTA00 Datasheet](https://www.kioxia.com/content/dam/kioxia/newidr/productinfo/datasheet/201910/DST_TC58NVG0S3HTA00-TDE_EN_31435.pdf)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [GitHub - crane-elec/rawnand_test](https://github.com/crane-elec/rawnand_test)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

## Contact

For any inquiries or questions, you can reach out to the project maintainer at [wipeseals@gmail.com](mailto:wipeseals@gmail.com).
