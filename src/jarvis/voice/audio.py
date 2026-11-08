from __future__ import annotations

import asyncio
import threading
import time


class AudioIO:
    """16 kHz PCM16 input and 24 kHz PCM16 output. Bounded buffers, no recording or disk writes."""

    def __init__(self):
        self.output = None
        self.buffer = bytearray()
        self.lock = threading.Lock()
        self.closed = False
        self.dropped_frames = 0

    def start_output(self):
        import sounddevice as sd

        if self.output:
            return
        self.closed = False

        def callback(outdata, frames, time_info, status):
            count = frames * 2
            with self.lock:
                chunk = bytes(self.buffer[:count])
                del self.buffer[:count]
            outdata[:] = chunk + bytes(count - len(chunk))

        self.output = sd.RawOutputStream(
            samplerate=24000, channels=1, dtype="int16", blocksize=480, callback=callback
        )
        self.output.start()

    def enqueue(self, data):
        with self.lock:
            if self.closed:
                return
            if len(self.buffer) + len(data) > 24000 * 2 * 10:
                self.buffer.clear()
                return
            self.buffer.extend(data)

    def clear(self):
        with self.lock:
            self.buffer.clear()
        # Output callback blocks are 20 ms. No long queued device writes to drain.

    async def capture(self, seconds=None):
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=8)
        accepting = True

        def offer(data):
            if not accepting:
                return
            if queue.full():
                queue.get_nowait()
                self.dropped_frames += 1
            queue.put_nowait(data)

        def callback(indata, frames, time_info, status):
            if accepting:
                loop.call_soon_threadsafe(offer, bytes(indata))

        end = time.monotonic() + seconds if seconds is not None else None
        with sd.RawInputStream(
            samplerate=16000, channels=1, dtype="int16", blocksize=1280, callback=callback
        ):
            try:
                while end is None or time.monotonic() < end:
                    try:
                        yield await asyncio.wait_for(queue.get(), 1)
                    except TimeoutError:
                        if end is not None and time.monotonic() >= end:
                            break
            finally:
                accepting = False
                while not queue.empty():
                    queue.get_nowait()

    def close(self):
        self.closed = True
        self.clear()
        if self.output:
            self.output.abort()
            self.output.close()
            self.output = None
