#!/usr/bin/env python3
"""
Surgical binary patch of a compiled AndroidManifest.xml (Android binary XML /
AXML format): locate the <uses-sdk android:minSdkVersion="..."> attribute's
raw integer value and overwrite ONLY those 4 bytes in place. Nothing else in
the file is touched (same length, same structure, same string pool, same
targetSdkVersion, same every other attribute/element).

This is a read-verify-then-write-in-place patch: it walks the real AXML chunk
structure (ResChunk_header / ResStringPool / ResXMLTree_node /
ResXMLTree_attrExt / ResXMLTree_attribute) rather than blind byte-search, so
it cannot accidentally hit an unrelated 4-byte sequence that happens to equal
27.
"""
import struct
import sys

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_RESOURCE_MAP_TYPE = 0x0180

UTF8_FLAG = 0x00000100


def read_string_pool(buf, pool_off, chunk_size):
    # ResStringPool_header (extends ResChunk_header, 28 bytes total header)
    (stringCount, styleCount, flags, stringsStart, stylesStart) = struct.unpack_from(
        '<IIIII', buf, pool_off + 8
    )
    is_utf8 = bool(flags & UTF8_FLAG)
    offsets = struct.unpack_from('<%dI' % stringCount, buf, pool_off + 28)
    strings = []
    data_base = pool_off + stringsStart
    for off in offsets:
        p = data_base + off
        if is_utf8:
            # utf8 length is encoded with a length-of-utf16-length prefix then
            # length-of-utf8-length prefix (both possibly 1 or 2 bytes)
            def read_len(pos):
                b0 = buf[pos]
                if b0 & 0x80:
                    b1 = buf[pos + 1]
                    return ((b0 & 0x7F) << 8) | b1, pos + 2
                return b0, pos + 1
            _, p = read_len(p)  # utf16 length (unused)
            u8len, p = read_len(p)
            s = buf[p:p + u8len].decode('utf-8', errors='replace')
        else:
            b0, b1 = buf[p], buf[p + 1]
            if b0 & 0x80 or b1 & 0x80:
                # two u16 length units
                lo = struct.unpack_from('<H', buf, p)[0]
                length = ((lo & 0x7FFF) << 16) | struct.unpack_from('<H', buf, p + 2)[0]
                p += 4
            else:
                length = struct.unpack_from('<H', buf, p)[0]
                p += 2
            s = buf[p:p + length * 2].decode('utf-16-le', errors='replace')
        strings.append(s)
    return strings


def main():
    in_path, out_path = sys.argv[1], sys.argv[2]
    old_val, new_val = int(sys.argv[3]), int(sys.argv[4])

    with open(in_path, 'rb') as f:
        buf = bytearray(f.read())

    (top_type, top_header_size, top_size) = struct.unpack_from('<HHI', buf, 0)
    assert top_type == RES_XML_TYPE, 'not an AXML file (type=0x%04x)' % top_type
    assert top_size == len(buf), 'AXML size field %d != actual file length %d' % (top_size, len(buf))

    strings = None
    pos = top_header_size
    patched = []

    while pos < len(buf):
        chunk_type, header_size, chunk_size = struct.unpack_from('<HHI', buf, pos)
        if chunk_type == RES_STRING_POOL_TYPE:
            strings = read_string_pool(buf, pos, chunk_size)
        elif chunk_type == RES_XML_START_ELEMENT_TYPE:
            assert strings is not None, 'START_ELEMENT before string pool?!'
            node_off = pos + header_size  # ResXMLTree_attrExt starts right after common node header+ext header per headerSize
            # headerSize for START_ELEMENT already covers: ResChunk_header(8) +
            # lineNumber(4) + comment(4) + ns(4) + name(4) + attributeStart(2) +
            # attributeSize(2) + attributeCount(2) + idIndex(2) + classIndex(2) +
            # styleIndex(2) = 36 normally (0x24).
            line_number, comment = struct.unpack_from('<II', buf, pos + 8)
            ns_idx, name_idx = struct.unpack_from('<II', buf, pos + 16)
            attr_start, attr_size, attr_count, id_idx, class_idx, style_idx = struct.unpack_from(
                '<HHHHHH', buf, pos + 24
            )
            elem_name = strings[name_idx] if name_idx != 0xFFFFFFFF else None
            attr_ext_start = pos + 16  # ResXMLTree_node is 16 bytes (8-byte ResChunk_header + lineNumber(4) + comment(4)); attrExt starts right after
            attrs_base = attr_ext_start + attr_start  # attributeStart is relative to the START of ResXMLTree_attrExt, per androidfw/ResourceTypes.h
            for i in range(attr_count):
                a_off = attrs_base + i * attr_size
                a_ns, a_name, a_raw_value = struct.unpack_from('<III', buf, a_off)
                size, res0, data_type, data = struct.unpack_from('<HBBI', buf, a_off + 12)
                attr_name = strings[a_name] if a_name != 0xFFFFFFFF else None
                if elem_name == 'uses-sdk' and attr_name == 'minSdkVersion':
                    data_field_off = a_off + 12 + 4  # offset of the 4-byte `data` value
                    assert data == old_val, (
                        'minSdkVersion currently %r, expected %r -- refusing to patch '
                        'blind' % (data, old_val)
                    )
                    assert data_type == 0x10, 'unexpected dataType 0x%02x for minSdkVersion (expected TYPE_INT_DEC 0x10)' % data_type
                    struct.pack_into('<I', buf, data_field_off, new_val)
                    patched.append({
                        'element': elem_name,
                        'attribute': attr_name,
                        'file_offset': data_field_off,
                        'old_value': old_val,
                        'new_value': new_val,
                    })
        if chunk_size == 0:
            raise RuntimeError('zero-size chunk at offset %d, aborting to avoid infinite loop' % pos)
        pos += chunk_size

    if not patched:
        raise SystemExit('ERROR: did not find <uses-sdk android:minSdkVersion> to patch -- aborting, nothing written')
    if len(patched) != 1:
        raise SystemExit('ERROR: found %d matching attributes, expected exactly 1 -- aborting' % len(patched))

    with open(out_path, 'wb') as f:
        f.write(buf)

    print('OK -- patched exactly 1 attribute, file length unchanged (%d bytes in, %d bytes out)' % (len(buf), len(buf)))
    for p in patched:
        print(p)


if __name__ == '__main__':
    main()
