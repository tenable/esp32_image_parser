# ESP32 Firmware Image to ELF
This tool can be used to convert a flash dump from an ESP32 into an ELF file.

Authors: @lynerc and @\_NickMiles\_

There are three actions:
- **show_partitions** - will display all of the partitions found in an image file.
- **dump_partition** - will dump the raw bytes of a specified partition into a file.
- **create_elf** - reconstruct an ELF file from an 'app' partition (e.g. ota_0).
- **dump_nvs** - will parse a specified NVS partition and dump its contents.

# Setup
`pip install -r requirements.txt`

# Example Usage
## Show all partitions
`$ python3 esp32_image_parser.py show_partitions espwroom32.bin`

## Dump a specific partition
Dumps to ble_data_out.bin

`$ python3 esp32_image_parser.py dump_partition espwroom32.bin -partition ble_data`

Dumps to ble_data.dump

`$ python3 esp32_image_parser.py dump_partition espwroom32.bin -partition ble_data -output ble_data.dump`

## Convert a specific app partition into an ELF file
Converts ota_0 partition into ELF. Writes to ota_0.elf

`$ python3 esp32_image_parser.py create_elf espwroom32.bin -partition ota_0 -output ota_0.elf`

## Dump a specific NVS partition
Dumps the nvs partition

`$ python3 esp32_image_parser.py dump_nvs esp32_flashdump.bin -partition nvs`

Dumps the nvs partition as a JSON

`$ python3 esp32_image_parser.py dump_nvs flashdump/esp32_flashdump.bin -partition nvs -nvs_output_type json`
