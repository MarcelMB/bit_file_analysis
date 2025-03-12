import matplotlib.pyplot as plt
from collections import defaultdict


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


def find_preamble_and_analyze_pixels(filename):
    """
    Look for preambles with both bit and byte reversal.
    """
    # Original firmware preamble (0x12345678)
    original_preamble = bytes.fromhex("12345678")

    # Apply both bit and byte reversal (as indicated by BufferFormatter)
    def reverse_bits(b):
        return int(format(b, "08b")[::-1], 2)

    # First reverse bytes, then reverse bits
    preamble_bytes = original_preamble[::-1]  # Byte reversal
    preamble_bytes = bytes(reverse_bits(b) for b in preamble_bytes)  # Bit reversal

    # Convert to bit pattern for searching
    preamble_bits = "".join(format(b, "08b") for b in preamble_bytes)
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

    # Store pixel data by frame number
    frame_pixels = defaultdict(list)

    with open(filename, "rb") as f:
        data = f.read()

    file_size = len(data)
    print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

    # Create bit streams
    bit_stream = "".join(format(b, "08b") for b in data)
    bit_stream_offset = "0" + bit_stream

    print("\nAnalyzing headers with both bit alignments...")

    # First find all preamble positions
    all_positions = []
    found_positions = set()

    # Define both possible preamble patterns
    preamble_bytes_patterns = [bytes.fromhex("1E6A2C48"), bytes.fromhex("8F351624")]
    preamble_bits = "".join(format(b, "08b") for b in preamble_bytes_patterns[0])

    for stream_idx, stream in enumerate([bit_stream, bit_stream_offset]):
        pos = 0
        while True:
            pos = stream.find(preamble_bits, pos)
            if pos == -1:
                break

            # Adjust byte position based on which stream
            if stream_idx == 0:
                byte_pos = pos // 8
                bit_offset = pos % 8
            else:
                byte_pos = (pos - 1) // 8
                bit_offset = (pos - 1) % 8

            # Verify the actual bytes match either pattern
            found_bytes = data[byte_pos : byte_pos + 4]
            if any(found_bytes == pattern for pattern in preamble_bytes_patterns):
                if byte_pos not in found_positions:
                    all_positions.append((byte_pos, bit_offset))
                    found_positions.add(byte_pos)

            pos += 1

    # Sort positions and start from second preamble
    all_positions.sort()
    frame_pixels = defaultdict(list)

    # Process headers starting from second position
    for count, (byte_pos, bit_offset) in enumerate(all_positions[1:]):
        header_start = byte_pos + 4
        header_data = data[header_start : header_start + 48]

        # Parse header fields
        values = {}
        for idx, field in enumerate(header_fields):
            word_start = idx * 4
            word_bytes = header_data[word_start : word_start + 4]
            bits_reversed = bytes(reverse_bits(b) for b in word_bytes)
            value = int.from_bytes(bits_reversed, "little") // 2
            values[field] = value

        # Print first 10 headers
        if count < 10:
            print(f"\nHeader {count} at byte {byte_pos:,} (0x{byte_pos:08X})")
            print("-" * 60)
            print(f"Preamble found: {' '.join(f'{b:02X}' for b in found_bytes)}")
            print(f"Raw header: {' '.join(f'{b:02X}' for b in header_data[:16])}...")
            print("-" * 60)
            for field, value in values.items():
                print(f"{field:20}: {value:,}")
            print("-" * 60)

        # Get pixel data
        pixel_start = header_start + 48
        pixel_data = data[pixel_start : pixel_start + 512]

        if pixel_data:
            min_pixel = min(pixel_data)
            frame_pixels[values["frame_num"]].append(min_pixel)

    # Calculate minimum pixel value per frame
    frame_mins = {frame: min(pixels) for frame, pixels in frame_pixels.items()}

    # Print frame number analysis
    frames = sorted(frame_mins.keys())
    print("\nFrame number analysis:")
    print(f"First frame: {frames[0]}")
    print(f"Last frame: {frames[-1]}")
    print(f"Number of frames: {len(frames)}")

    # Check for gaps
    gaps = []
    for i in range(len(frames) - 1):
        diff = frames[i + 1] - frames[i]
        if diff > 1:
            gaps.append((frames[i], frames[i + 1], diff))

    if gaps:
        print("\nFound gaps in frame numbers:")
        for start, end, size in gaps:
            print(f"Gap between frame {start} and {end} (size: {size})")
    else:
        print("\nFrames are sequential (no gaps)")

    # Print frames with non-zero min values
    print("\nFrames with non-zero minimum values:")
    for frame in frames:
        if frame_mins[frame] > 0:
            print(f"Frame {frame}: min={frame_mins[frame]}")

    # Plot results
    plt.figure(figsize=(12, 6))
    plt.plot(frames, [frame_mins[f] for f in frames], "-")
    plt.title("Minimum Pixel Value per Frame")
    plt.xlabel("Frame Number")
    plt.ylabel("Minimum Pixel Value")
    plt.grid(True)
    plt.savefig("min_pixels_per_frame.png")
    plt.show()
    plt.close()

    print("\nAnalysis complete!")
    print(f"Processed {len(frame_pixels)} unique frames")
    print(f"Total preambles found: {len(found_positions)}")


def analyze_preamble_transformations():
    """Analyze all possible transformations of the preamble"""
    # Original firmware preamble
    preamble = bytes.fromhex("12345678")

    # Function to reverse bits in a byte
    def reverse_bits(b):
        return int(format(b, "08b")[::-1], 2)

    print("\nPreamble transformation analysis:")
    print("-" * 60)

    # 1. Original
    print("Original:              ", " ".join(f"{b:02X}" for b in preamble))

    # 2. Bit-reversed only
    bit_reversed = bytes(reverse_bits(b) for b in preamble)
    print("Bit-reversed:          ", " ".join(f"{b:02X}" for b in bit_reversed))

    # 3. Byte-reversed only
    byte_reversed = preamble[::-1]
    print("Byte-reversed:         ", " ".join(f"{b:02X}" for b in byte_reversed))

    # 4. Both bit and byte reversed
    both_reversed = bytes(reverse_bits(b) for b in byte_reversed)
    print("Bit+byte reversed:     ", " ".join(f"{b:02X}" for b in both_reversed))

    print("\nWhat we find in file:   8F 35 16 24")
    print("-" * 60)


if __name__ == "__main__":
    analyze_preamble_transformations()
    filename = "test_LED1.bin"
    find_preamble_and_analyze_pixels(filename)
