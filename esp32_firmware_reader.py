import struct
import sys
import argparse
from makeelf.elf import *

PART_TYPES = {
  0x00: "APP",
  0x01: "DATA"
}

PART_SUBTYPES_APP = {
  0x00: "FACTORY",
  0x20: "TEST"
}

for i in range(0,16):
  PART_SUBTYPES_APP[0x10 | i] = "ota_" + str(i)

PART_SUBTYPES_DATA = {
  0x00: "OTA",
  0x01: "RF",
  0x02: "WIFI",
  0x04: "NVS"
}

def print_verbose(verbose, value):
    if verbose:
        print(value)

def read_partition_table(fh, verbose=False):
    fh.seek(0x8000)
    partition_table = {}

    print_verbose(verbose, "reading partition table...")
    for i in range(0, 95): # max 95 partitions
        magic = fh.read(2)
        # end marker
        if(magic == b'\xff\xff'):
            data = magic + fh.read(30)
            if data == b'\xff'*32:
                print_verbose(verbose,"Done")
                return partition_table
        # md5sum
        elif(magic == b'\xeb\xeb'):
            data = magic + fh.read(30)
            print_verbose(verbose,"MD5sum: ")
            print_verbose(verbose,data[16:].hex())
            continue
        # is partition?
        elif(magic[0] != 0xAA or magic[1] != 0x50):
            return partition_table

        print_verbose(verbose, "entry %d:" % (i))
        part_type = ord(fh.read(1))
        part_subtype = ord(fh.read(1))
        part_offset = struct.unpack("<I", fh.read(4))[0]
        part_size = struct.unpack("<I", fh.read(4))[0]
        part_label = fh.read(16).decode('ascii').rstrip('\x00')
        part_flags = fh.read(4)

        part_type_label = "unknown"
        if(part_type in PART_TYPES):
            part_type_label = PART_TYPES[part_type]

        part_subtype_label = "unknown"
        if(part_type_label == "APP" and part_subtype in PART_SUBTYPES_APP):
            part_subtype_label = PART_SUBTYPES_APP[part_subtype]
        if(part_type_label == "DATA" and part_subtype in PART_SUBTYPES_DATA):
            part_subtype_label = PART_SUBTYPES_DATA[part_subtype]

        print_verbose(verbose, "  label      : " + part_label)
        print_verbose(verbose, "  offset     : " + hex(part_offset))
        print_verbose(verbose, "  length     : " + str(part_size))
        print_verbose(verbose, "  type       : " + str(part_type) + " [" + part_type_label + "]")
        print_verbose(verbose, "  sub type   : " + str(part_subtype) + " [" + part_subtype_label + "]")
        print_verbose(verbose, "")

        partition_table[part_label] = {"type":part_type, "subtype":part_subtype, "offset":part_offset, "size":part_size, "flags":part_flags}

def dump_bytes(fh, offset, length, filename, verbose=False):
    print_verbose(verbose, "Dumping " + str(length) + " bytes to " + filename)
    fh.seek(offset)
    data = fh.read(length)
    fh1 = open(filename, 'wb')
    fh1.write(data)
    fh1.close()
    return (filename, data)
