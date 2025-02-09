import argparse
from esp32_image_parser import image2elf

def main():
    desc = 'ESP32 Firmware Image Parser Utility'
    arg_parser = argparse.ArgumentParser(description=desc)
    arg_parser.add_argument('input', help='App partition input file. (If the app partition is part of a complete firmware file, use "esp32_image_parser image2elf" instead.)')
    arg_parser.add_argument('output', help='Output file name')
    arg_parser.add_argument('-v', default=False, help='Verbose output', action='store_true')

    args = arg_parser.parse_args()
    image2elf(args.input, args.output, args.v)


if __name__ == '__main__':
    main()
