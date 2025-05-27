#!/usr/bin/env python

# Convert an ESP 32 OTA partition into an ELF
import sys
import json
import os, argparse
from makeelf.elf import *
from esptool import *
from esptool.bin_image import *
from esp32_firmware_reader import *
from read_nvs import *

def image_base_name(path):
    filename_w_ext = os.path.basename(path)
    filename, ext = os.path.splitext(filename_w_ext)
    return filename

# section header flags
def calcShFlg(flags):
    mask = 0
    if 'W' in flags:
        mask |= SHF.SHF_WRITE
    if 'A' in flags:
        mask |= SHF.SHF_ALLOC
    if 'X' in flags:
        mask |= SHF.SHF_EXECINSTR
            
    return mask

# program header flags
def calcPhFlg(flags):
    p_flags = 0
    if 'r' in flags:
        p_flags |= PF.PF_R
    if 'w' in flags:
        p_flags |= PF.PF_W
    if 'x' in flags:
        p_flags |= PF.PF_X
    return p_flags

def image2elf(filename, output_file, verbose=False):
    image = LoadFirmwareImage('esp32', filename)

    # parse image name
    # e.g. 'image.bin' turns to 'image'
    image_name = image_base_name(filename)

    elf = ELF(e_machine=EM.EM_XTENSA, e_data=ELFDATA.ELFDATA2LSB)
    elf.Elf.Ehdr.e_entry = image.entrypoint

    print_verbose(verbose, "Entrypoint " + str(hex(image.entrypoint)))

    # maps segment names to ELF sections
    section_map = {
        'DROM'                      : '.flash.rodata',
        'BYTE_ACCESSIBLE, DRAM'     : '.dram0.data',
        'BYTE_ACCESSIBLE, DRAM, DMA': '.dram0.data',
        'IROM'                      : '.flash.text',
        #'RTC_IRAM'                  : '.rtc.text' TODO
    }

    # map to hold pre-defined ELF section header attributes
    # http://man7.org/linux/man-pages/man5/elf.5.html
    # ES    : sh_entsize
    # Flg   : sh_flags
    # Lk    : sh_link
    # Inf   : sh_info
    # Al    : sh_addralign
    sect_attr_map = {
            '.flash.rodata' : {'ES':0x00, 'Flg':'WA',  'Lk':0, 'Inf':0, 'Al':16},
            '.dram0.data'   : {'ES':0x00, 'Flg':'WA',  'Lk':0, 'Inf':0, 'Al':16},
            '.iram0.vectors': {'ES':0x00, 'Flg':'AX',  'Lk':0, 'Inf':0, 'Al':4},
            '.iram0.text'   : {'ES':0x00, 'Flg':'AX',  'Lk':0, 'Inf':0, 'Al':4},
            '.flash.text'   : {'ES':0x00, 'Flg':'AX',  'Lk':0, 'Inf':0, 'Al':4}
    }
    # TODO rtc not accounted for

    section_data = {}

    ##### build out the section data #####
    ######################################
    iram_seen = False
    for seg in sorted(image.segments, key=lambda s:s.addr):

        # name from image
        segment_name = ", ".join([seg_range[2] for seg_range in image.ROM_LOADER.MEMORY_MAP if seg_range[0] <= seg.addr < seg_range[1]])

        # TODO when processing an image, there was an empty segment name?
        if segment_name == '':
            continue

        section_name = ''
        # handle special case
        # iram is split into .vectors and .text
        # .iram0.vectors seems to be the first one.
        if segment_name == 'IRAM':
            if iram_seen == False:
                section_name = '.iram0.vectors'
            else:
                section_name = '.iram0.text'
            iram_seen = True
        else:
            if segment_name in section_map:
                section_name = section_map[segment_name]
            else:
                print("Unsure what to do with segment: " + segment_name)

        # if we have a mapped segment <-> section
        # add the elf section
        if section_name != '':
            # might need to append to section (e.g. IRAM is split up due to alignment)
            if section_name in section_data:
                    section_data[section_name]['data'] += seg.data
            else:
                section_data[section_name] = {'addr':seg.addr, 'data':seg.data}

    ##### append the sections #####
    ###############################
    for name in section_data.keys():
        data = section_data[name]['data']
        addr = section_data[name]['addr']
        # build the section out as much as possible
        # if we already know the attribute values
        if name in sect_attr_map:
            sect = sect_attr_map[name]
            flg = calcShFlg(sect['Flg'])
            elf._append_section(name, data, addr,SHT.SHT_PROGBITS, flg, sect['Lk'], sect['Inf'], sect['Al'], sect['ES'])
        else:
            elf.append_section(name, data, addr)

    elf.append_special_section('.strtab')
    elf.append_special_section('.symtab')
    add_elf_symbols(elf)

    # segment flags
    # TODO rtc
    segments = {
        '.flash.rodata' : 'rw',
        '.dram0.data'   : 'rw',
        '.iram0.vectors': 'rwx',
        '.flash.text'   : 'rx'
    }

    # there is an initial program header that we don't want...
    elf.Elf.Phdr_table.pop()

    bytes(elf) # kind of a hack, but __bytes__() calculates offsets in elf object

    # TODO this logic might change as we add support for rtc
    size_of_phdrs = len(Elf32_Phdr()) * len(segments) # to pre-calculate program header offsets

    ##### add the segments ####
    ###########################
    print_verbose(verbose, "\nAdding program headers")
    for (name, flags) in segments.items():

        if (name == '.iram0.vectors'):
            # combine these
            size = len(section_data['.iram0.vectors']['data']) + len(section_data['.iram0.text']['data'])
        else:
            size = len(section_data[name]['data'])
        
        p_flags = calcPhFlg(flags)
        addr = section_data[name]['addr']
        align = 0x1000
        p_type = PT.PT_LOAD

        shstrtab_hdr, shstrtab = elf.get_section_by_name(name)
        offset = shstrtab_hdr.sh_offset + size_of_phdrs # account for new offset

        # build program header
        Phdr = Elf32_Phdr(PT.PT_LOAD, p_offset=offset, p_vaddr=addr,
                p_paddr=addr, p_filesz=size, p_memsz=size,
                p_flags=p_flags, p_align=align, little=elf.little)

        print_verbose(verbose, name + ": " + str(Phdr))
        elf.Elf.Phdr_table.append(Phdr)

    # write out elf file
    if output_file is not None:
        out_file = output_file
    else:
        out_file = image_name + '.elf'
    print("\nWriting ELF to " + out_file + "...")
    fd = os.open(out_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.write(fd, bytes(elf))
    os.close(fd)

def add_elf_symbols(elf):

    fh = open("symbols_dump.txt", "r")
    lines = fh.readlines()

    bind_map = {"LOCAL" : STB.STB_LOCAL, "GLOBAL" : STB.STB_GLOBAL, "WEAK" : STB.STB_WEAK}
    type_map = {"NOTYPE": STT.STT_NOTYPE, "OBJECT" : STT.STT_OBJECT, "FUNC" : STT.STT_FUNC, "FILE" : STT.STT_FILE}

    for line in lines:
        line = line.split()
        sym_binding = line[4]
        sym_type = line[3]
        sym_size = int(line[2])
        sym_val = int(line[1], 16)
        sym_name = line[7]
                                    # ABS
        elf.append_symbol(sym_name, 0xfff1, sym_val, sym_size, sym_binding=bind_map[sym_binding], sym_type=type_map[sym_type])

def flash_dump_to_elf(filename, partition):
    fh = open(filename, 'rb')
    part_table = read_partition_table(fh)
    fh.close()
    return part_table

def dump_partition(fh, part_name, offset, size, dump_file):
    print("Dumping partition '" + part_name + "' to " + dump_file)
    dump_bytes(fh, offset, size, dump_file)

def main():
    desc = 'ESP32 Firmware Image Parser Utility'
    arg_parser = argparse.ArgumentParser(description=desc)
    arg_parser.add_argument('action', choices=['show_partitions', 'dump_partition', 'create_elf', 'dump_nvs'], help='Action to take')
    arg_parser.add_argument('input', help='Firmware image input file')
    arg_parser.add_argument('-output', help='Output file name')
    arg_parser.add_argument('-nvs_output_type', help='output type for nvs dump', type=str, choices=["text","json"], default="text")
    arg_parser.add_argument('-partition', help='Partition name (e.g. ota_0)')
    arg_parser.add_argument('-v', default=False, help='Verbose output', action='store_true')

    args = arg_parser.parse_args()

    with open(args.input, 'rb') as fh:
        verbose = False
        # read_partition_table will show the partitions if verbose
        if args.action == 'show_partitions' or args.v is True:
            verbose = True

        # parse that ish
        part_table = read_partition_table(fh, verbose)

        if args.action in ['dump_partition', 'create_elf', 'dump_nvs']:
            if (args.partition is None):
                print("Need partition name")
                return

            part_name = args.partition
            
            if args.action == 'dump_partition' and args.output is not None:
                dump_file = args.output
            else:
                dump_file = part_name + '_out.bin'

            if part_name in part_table:
                part = part_table[part_name]
            
                if args.action == 'dump_partition':
                    dump_partition(fh, part_name, part['offset'], part['size'], dump_file)
                if args.action == 'create_elf':
                    # can only generate elf from 'app' partition type
                    if part['type'] != 0:
                        print("Uh oh... bad partition type. Can't convert to ELF")
                    else:
                        if args.output is None:
                            print("Need output file name")
                        else:
                            dump_partition(fh, part_name, part['offset'], part['size'], dump_file)
                            # we have to load from a file
                            output_file = args.output
                            image2elf(dump_file, output_file, verbose)
                elif args.action == 'dump_nvs':
                    if part['type'] != 1 or part['subtype'] != 2: # Wifi NVS partition (4 is for encryption key)
                        print("Uh oh... bad partition type. Can only dump NVS partition type.")
                    else:
                        dump_partition(fh, part_name, part['offset'], part['size'], dump_file)
                        with open(dump_file, 'rb') as fh:
                            if(args.nvs_output_type != "text"):
                                sys.stdout = open(os.devnull, 'w') # block print()
                            pages = read_nvs_pages(fh)
                            sys.stdout = sys.stdout = sys.__stdout__ # re-enable print()
                            if(args.nvs_output_type == "json"):
                                print(json.dumps(pages))
            else:
                print("Partition '" + part_name + "' not found.")

if __name__ == '__main__':
    main()
