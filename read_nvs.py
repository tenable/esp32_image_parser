import os
import struct
import base64
import binascii
from hexdump import hexdump

nvs_types =  {
  0x01: "U8",
  0x11: "I8",
  0x02: "U16",
  0x12: "I16",
  0x04: "U32",
  0x14: "I32",
  0x08: "U64",
  0x18: "I64",
  0x21: "STR",
  0x41: "BLOB",
  0x42: "BLOB_DATA",
  0x48: "BLOB_IDX",
  0xFF: "ANY"
}

entry_state_descs = {
        3: "Empty",
        2: "Written",
        0: "Erased"
}

nvs_sector_states = {
        0xFFFFFFFF : "EMPTY",
        0xFFFFFFFE : "ACTIVE",
        0xFFFFFFFC : "FULL",
        0xFFFFFFF8 : "FREEING",
        0xFFFFFFF0 : "CORRUPT"
}

namespaces = {}

def parse_nvs_entries(entries, entry_state_bitmap):
    entries_out = []
    i = 0
    while i < 126:
        entry_data = {}
        print("  Entry %d" % (i))
        print("  Bitmap State : %s" % (entry_state_descs[int(entry_state_bitmap[i])]))
        entry_data["entry_state"] = entry_state_descs[int(entry_state_bitmap[i])]

        entry = entries[i]
        state = entry_state_bitmap[i]
    
        entry_ns = entry[0]
        entry_type = entry[1]
        entry_span = entry[2]
        chunk_index = entry[3]

        key = entry[8:24]

        data = entry[24:]
        if(entry_type == 0):
            i += 1
            continue

        if(nvs_types[entry_type] == "ANY"):
            i += 1
            continue

        decoded_key = ''
        for c in key:
            if(c == 0):
                break
            decoded_key += chr(c)

        key = decoded_key

        print("    Written Entry %d" % (i))
        print("      NS Index : %d" % (entry_ns))
        entry_data["entry_ns_index"] = entry_ns

        if(entry_ns != 0 and entry_ns in namespaces):
            print("          NS : %s" % (namespaces[entry_ns]))
            entry_data["entry_ns"] = namespaces[entry_ns]

        print("      Type : %s" % (nvs_types[entry_type]))
        print("      Span : %d" % (entry_span))
        print("      ChunkIndex : %d" % (chunk_index))
        print("      Key : " + key)
        entry_data["entry_type"] = nvs_types[entry_type]
        entry_data["entry_span"] = entry_span
        entry_data["entry_chunk_index"] = chunk_index
        entry_data["entry_key"] = key


        if(nvs_types[entry_type] == "U8"):
            data = struct.unpack("<B", data[0:1])[0]
            print("      Data (U8) : %d" % (data))
            if(entry_ns == 0):
                namespaces[data] = key
            entry_data["entry_data_type"] = "U8"
            entry_data["entry_data"] = data

        elif(nvs_types[entry_type] == "I8"):
            data = struct.unpack("<b", data[0:1])[0]
            print("      Data (I8) : %d" % (data))
            entry_data["entry_data_type"] = "I8"
            entry_data["entry_data"] = data

        elif(nvs_types[entry_type] == "U16"):
            data = struct.unpack("<H", data[0:2])[0]
            print("      Data (U16) : %d" % (data))
            entry_data["entry_data_type"] = "U16"
            entry_data["entry_data"] = data
        
        elif(nvs_types[entry_type] == "I16"):
            data = struct.unpack("<h", data[0:2])[0]
            print("      Data (I16) : %d" % (data))
            entry_data["entry_data_type"] = "I16"
            entry_data["entry_data"] = data

        elif(nvs_types[entry_type] == "U32"):
            data = struct.unpack("<I", data[0:4])[0]
            print("      Data (U32) : %d" % (data))
            entry_data["entry_data_type"] = "U32"
            entry_data["entry_data"] = data
        
        elif(nvs_types[entry_type] == "I32"):
            data = struct.unpack("<i", data[0:4])[0]
            print("      Data (I32) : %d" % (data))
            entry_data["entry_data_type"] = "I32"
            entry_data["entry_data"] = data

        elif(nvs_types[entry_type] == "STR"):
            str_size = struct.unpack("<H", data[0:2])[0]
            print("      String :")
            entry_data["entry_data_type"] = "STR"
            print("        Size : %d " % (str_size))
            entry_data["entry_data_size"] = str_size
            data = b'' 
            for x in range(1, entry_span):
                i += 1
                data += entries[i]
            data = data[0:str_size-1].decode('ascii')
            print("        Data : %s" % (data))
            entry_data["entry_data"] = str(data)

        elif(nvs_types[entry_type] == "BLOB_DATA"):
            blob_data_size = struct.unpack("<H", data[0:2])[0]
            print("      Blob Data :")
            entry_data["entry_data_type"] = "BLOB_DATA"
            print("        Size : %d " % (blob_data_size))
            entry_data["entry_data_size"] = blob_data_size
            data = b'' 
            for x in range(1, entry_span):
                i += 1
                data += entries[i]
            print("        Data :")
            hexdump(data[:blob_data_size])
            entry_data["entry_data"] = base64.b64encode(data[:blob_data_size]).decode('ascii')

        elif(nvs_types[entry_type] == "BLOB"):
            blob_size = struct.unpack("<H", data[0:2])[0]
            print("      Data (Blob) :")
            entry_data["entry_data_type"] = "BLOB"
            print("        Size : %d " % (blob_size))
            entry_data["entry_data_size"] = blob_size
            data = b'' 
            for x in range(1, entry_span):
                i += 1
                data += entries[i]
            print("        Data :")
            hexdump(data[:blob_size])
            entry_data["entry_data"] = base64.b64encode(data[:blob_size]).decode('ascii')

        elif(nvs_types[entry_type] == "BLOB_IDX"):
            idx_size = struct.unpack("<I", data[0:4])[0]
            chunk_count = struct.unpack("<B", data[5:6])[0]
            chunk_start = struct.unpack("<B", data[6:7])[0]
            print("      Blob IDX :")
            entry_data["entry_data_type"] = "BLOB_IDX"
            print("        Size        : %d " % (idx_size))
            print("        Chunk Count : %d " % (chunk_count))
            print("        Chunk Start  : %d " % (chunk_start))
            entry_data["entry_data_size"] = idx_size
            entry_data["entry_data_chunk_count"] = chunk_count
            entry_data["entry_data_chunk_start"] = chunk_start

        else:
            print("      Data : %s" % (str(data)))
            entry_data["entry_data"] = str(data)

        entries_out.append(entry_data)
        i += 1
        print("")
    return entries_out

def read_nvs_pages(fh):
    pages = []
    fh.seek(0, os.SEEK_END)
    file_len = fh.tell()

    sector_pos = 0
    x = 0
    while(sector_pos < file_len):
        page_data = {}

        fh.seek(sector_pos)
        page_state = nvs_sector_states[struct.unpack("<I", fh.read(4))[0]]
        seq_no = struct.unpack("<I", fh.read(4))[0]
        version = (ord(fh.read(1)) ^ 0xff) + 1

        print("Page %d" % (x))
        print("  page state : %s" % (page_state))
        print("  page seq no. : %d" % (seq_no))
        print("  page version : %d" % (version))
       
        page_data["page_state"] = page_state
        page_data["page_seq_no"] = seq_no
        page_data["page_version"] = version

        fh.read(19) # unused

        crc_32 = struct.unpack("<I", fh.read(4))[0]
        print("  crc 32 : %d" % (crc_32))
        page_data["page_crc_32"] = crc_32

        entry_state_bitmap = fh.read(32)
        entry_state_bitmap_decoded = ''

        for entry_num in range(0, 126):
            bitnum = entry_num * 2
            byte_index = int(bitnum / 8)
            temp = entry_state_bitmap[byte_index]
            
            temp = temp >> (6 - (bitnum % 8))
            temp = temp & 3
            entry_state_bitmap_decoded = entry_state_bitmap_decoded + str(temp)

        print("  page entry state bitmap (decoded) : %s" % (entry_state_bitmap_decoded))
        page_data["page_entry_state_bitmap"] = entry_state_bitmap_decoded 
        sector_pos += 4096
        x += 1

        entries = []
        entry_data = ''
        for entry in entry_state_bitmap_decoded:
            entry_data = fh.read(32)
            entries.append(entry_data)

        page_data["entries"] = parse_nvs_entries(entries, entry_state_bitmap_decoded)

        print("")
        print("")
        print("------------------------------------------------------------------------------")
        print("")
        pages.append(page_data)

    print("")
    return pages

#parser = argparse.ArgumentParser()
#parser.add_argument("nvs_bin_file", help="nvs partition binary file", type=str)
#parser.add_argument("-output_type", help="output type", type=str, choices=["text", "json"], default="text")

#args = parser.parse_args()

#with open(args.nvs_bin_file, 'rb') as fh:
#  if(args.output_type != "text"):
#    sys.stdout = open(os.devnull, 'w') # block print()

#  pages = read_pages(fh)

#  sys.stdout = sys.stdout = sys.__stdout__ # re-enable print()

#  if(args.output_type == "json"):
#      print(json.dumps(pages))

