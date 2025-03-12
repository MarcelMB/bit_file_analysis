def reverse_bits(byte):
    """Reverse the bits in a byte"""
    return int(format(byte, "08b")[::-1], 2)


def reverse_32bit_word(word_bytes):
    """Try different ways of reversing a 32-bit word"""
    # Original bytes
    word_orig = word_bytes

    # Reverse bytes then bits
    word_rev_bytes = word_bytes[::-1]
    word_rev_bits = bytes(reverse_bits(b) for b in word_bytes)

    # Reverse both
    word_rev_both = bytes(reverse_bits(b) for b in word_bytes[::-1])

    return [word_orig, word_rev_bytes, word_rev_bits, word_rev_both]


def analyze_blocks(filename, block_size=512, header_len=384):
    """
    Analyze blocks looking for:
    1. Frame numbers (~18727) in bit-reversed data
    2. Preamble (0x12345678) in bit-reversed form
    3. Frame buffer count (0-7)
    """
    with open(filename, "rb") as f:
        data = f.read()

    file_size = len(data)
    num_blocks = file_size // block_size
    header_bytes = header_len // 8

    print(f"File size: {file_size} bytes ({file_size / 1024 / 1024:.1f} MB)")
    print(f"Number of complete blocks: {num_blocks}")
    print(f"Header size: {header_bytes} bytes")

    # Create bit-reversed version of preamble
    preamble = bytes.fromhex("12345678")
    preamble_reversed = bytes(reverse_bits(b) for b in preamble)
    print("\nPreamble patterns we're looking for:")
    print("Original:", " ".join(f"{b:02X}" for b in preamble))
    print("Bit-reversed:", " ".join(f"{b:02X}" for b in preamble_reversed))

    print("\nAnalyzing blocks...")
    for block_num in range(num_blocks - 8):
        block_start = block_num * block_size

        # Look at a larger window to catch preamble
        window = data[block_start - 32 if block_start >= 32 else 0 : block_start + 64]
        window_reversed = bytes(reverse_bits(b) for b in window)

        # Check for preamble patterns
        if preamble in window or preamble_reversed in window:
            print(
                f"\nFound preamble pattern near block {block_num} (0x{block_start:08X})"
            )
            print("Window:", " ".join(f"{b:02X}" for b in window))
            print("Window (reversed):", " ".join(f"{b:02X}" for b in window_reversed))

        # Look at header values
        header = data[block_start : block_start + 32]
        header_reversed = bytes(reverse_bits(b) for b in header)

        # Try both endianness
        for byte_order in ["little", "big"]:
            values = [
                int.from_bytes(header_reversed[i : i + 4], byte_order)
                for i in range(0, len(header_reversed), 4)
            ]

            # Debug: Show more values that might be interesting
            interesting = any(
                18700 < v < 18900  # Frame numbers
                or 0 <= v < 8  # Buffer count
                or 149000 < v < 151000  # Buffer numbers from CSV
                for v in values
            )

            if interesting:
                print(
                    f"\nInteresting values at block {block_num} (0x{block_start:08X}):"
                )
                print(f"Values ({byte_order}-endian):", values)
                print("Original bytes:", " ".join(f"{b:02X}" for b in header))
                print("Bit-reversed:", " ".join(f"{b:02X}" for b in header_reversed))

                # Show previous bytes for context
                if block_start >= 32:
                    prev = data[block_start - 32 : block_start]
                    prev_reversed = bytes(reverse_bits(b) for b in prev)
                    print("Previous (original):", " ".join(f"{b:02X}" for b in prev))
                    print(
                        "Previous (reversed):",
                        " ".join(f"{b:02X}" for b in prev_reversed),
                    )


def find_preamble_and_header(filename):
    """
    Look for all preambles (0x1E6A2C48) and analyze their headers.
    Using bit-reversed + little-endian interpretation.
    """
    preamble_bits = "00011110011010100010110001001000"
    preamble_len = len(preamble_bits)
    header_fields = [
        "linked_list",
        "frame_num",
        "buffer_count",
        "frame_buffer_count",
        "write_buffer_count",
        "dropped_buffer_count",
        "timestamp",
        "write_timestamp",
        "pixel_count",
        "battery_voltage_raw",
        "input_voltage_raw",
        "unix_time",
    ]

    with open(filename, "rb") as f:
        data = f.read()

    file_size = len(data)
    print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

    # First count total preambles
    bit_stream = "".join(format(b, "08b") for b in data)
    total_count = bit_stream.count(preamble_bits)
    print(f"\nTotal preambles in file: {total_count}")

    print("\nAnalyzing headers (bit-reversed, little-endian)...")

    # Find all preambles
    pos = 0
    count = 0
    last_pos = None

    while True:
        pos = bit_stream.find(preamble_bits, pos)
        if pos == -1:
            break

        byte_pos = pos // 8
        bit_offset = pos % 8

        if last_pos is not None:
            diff = byte_pos - last_pos
            print(f"Distance from last: {diff} bytes")
        last_pos = byte_pos

        # Get header data
        header_start = byte_pos + 4  # Skip preamble
        header_data = data[header_start : header_start + 48]
        header_reversed = bytes(reverse_bits(b) for b in header_data)

        print(
            f"\nPreamble {count} at byte {byte_pos:,} (0x{byte_pos:08X}), bit offset {bit_offset}"
        )

        # Parse header fields
        values = {}
        for idx, field in enumerate(header_fields):
            word_start = idx * 4
            word_bytes = header_reversed[word_start : word_start + 4]
            if len(word_bytes) == 4:
                value = int.from_bytes(word_bytes, "little")
                values[field] = value

        # Print key fields
        print(
            f"linked_list: {values['linked_list']}, "
            f"frame_num: {values['frame_num']}, "
            f"buffer_count: {values['buffer_count']}, "
            f"frame_buffer_count: {values['frame_buffer_count']}"
        )

        count += 1
        pos += 1

        if count >= 20:  # Show first 20 for now
            print(f"\nShowing first {count} of {total_count} preambles...")
            break


if __name__ == "__main__":
    filename = "test_.bin"
    find_preamble_and_header(filename)
