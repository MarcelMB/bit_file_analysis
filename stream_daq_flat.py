import pdb

import cv2
import skvideo.io
from bitstring import BitArray, Bits
from pathlib import Path
import numpy as np
from matplotlib import pyplot as plt
from skvideo.io import FFmpegWriter

preamble = b'\x124Vx'

def iter_chunks(binfile: Path, preamble: int, read_length: int):
    """StreamDaq._fpga_recv"""
    cur_buffer = BitArray()

    pre = Bits(preamble)
    pre = pre[::-1]
    i = 0

    with open(binfile, "rb") as f:
        while True:
            i += 1
            buf = f.read(read_length)
            if len(buf) < read_length:
                break
            dat = BitArray(buf)

            cur_buffer = cur_buffer + dat
            pre_pos = list(cur_buffer.findall(pre))
            for buf_start, buf_stop in zip(pre_pos[:-1], pre_pos[1:]):
                yield cur_buffer[buf_start:buf_stop].tobytes()
            if pre_pos:
                cur_buffer = cur_buffer[pre_pos[-1]:]

def split_buffers(data: bytes):
    """bit_operation.BufferFormatter"""
    header_len_words = int(384 / 32)
    preamble_len_words = int(len(Bits(preamble)) / 32)
    header_data = data[preamble_len_words:header_len_words]
    payload_data = data[header_len_words:]
    return header_data, payload_data


def buffer_npix() -> list[int]:
    """StreamDaq.buffer_npix"""
    px_per_frame = 200 * 200
    byte_per_word = np.iinfo(np.int32).bits / np.iinfo(np.int8).bits

    px_per_buffer = (
            10 * 512
            - 384 / np.iinfo(np.int8).bits
            - 10 * byte_per_word
    )
    quotient, remainder = divmod(px_per_frame, px_per_buffer)
    return [int(px_per_buffer)] * int(quotient) + [int(remainder)]

def buffer_to_array(buffer: bytes) -> np.ndarray:
    """bit_operation.BufferFormatter"""
    padding_length = (4 - (len(buffer) % 4)) % 4
    buffer = buffer + b"\x00" * padding_length
    buffer = np.frombuffer(buffer, dtype=np.uint32)
    return buffer


def reverse_buffer(arr: np.array) -> np.array:
    """bit_operation.BufferFormatter"""
    arr = np.unpackbits(arr.view(np.uint8)).reshape(-1, 32)[:, ::-1]
    arr = np.packbits(arr).view(np.uint32)
    arr = arr.byteswap()
    arr = arr.view(np.uint8)
    return arr

def split_frames(arr: np.ndarray) -> np.ndarray:
    # hardcoding bc somehow i forgot how modulo works
    padded = np.pad(catted, (0, 1644))
    frame = padded.reshape((-1, 200))
    frames = np.split(frame, np.arange(200, frame.shape[0], 200))
    return frames

def write_video(frames):
    fourcc = cv2.VideoWriter_fourcc(*'Y800')
    writer = cv2.VideoWriter('test_.avi', fourcc, 30, (200, 200))
    for frame in frames:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        writer.write(frame)
    writer.release()

def write_video_ffmpeg(frames):
    writer = FFmpegWriter("test_ffmpeg.avi", outputdict={
        "-vcodec": "rawvideo",
        "-f": "avi",
        "-filter:v": "format=gray"
    })
    for frame in frames:
        writer.writeFrame(frame)
    writer.close()




if __name__ == "__main__":
    binfile = Path("test_.bin")
    chunks = []
    raw_buffers = []
    buffers = []
    frames = []
    read_length = int(max(buffer_npix()) * 8 / 8 / 16) * 16
    for chunk in iter_chunks(binfile, preamble=preamble, read_length=read_length):
        chunks.append(chunk)
        header, buffer = split_buffers(chunk)
        buffer = buffer_to_array(buffer)
        raw_buffers.append(buffer)
        buffer = reverse_buffer(buffer)
        buffers.append(buffer)

    catted = np.concat(buffers)
    smalls = catted[catted < 48]
    # plt.ion()
    # plt.hist(smalls, bins=48)

    frames = split_frames(catted)
    write_video(frames)
    write_video_ffmpeg(frames)









