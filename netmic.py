import socket
import pyaudio
import logging
import time
import threading
import argparse
import sys
import wave
from queue import Queue, Empty, Full

lock = threading.Lock()
recording = False
data_queue = Queue(maxsize=20)

def send_audio(sock: socket.socket, data) -> bool:
    totalsent = 0
    data_len = len(data)
    logging.debug("Sending sampled %d audio bytes over network", data_len)
    while totalsent < data_len:
        sent = 0
        try:
            sent = sock.send(data[totalsent:])
            if sent == 0:
                raise RuntimeError("Socket connection broke")
        except Exception as err:
            logging.error("Error while sending audio data over network: %s", err)
            return False
        totalsent = totalsent + sent
    logging.debug("Sent %d bytes over network", data_len)
    return True

def process_audio(sock: socket.socket):
    global data_queue
    global lock
    global recording
    try:
        while True:
            # Get next data chunk
            data = data_queue.get(block=True, timeout=5.0)
            # Send audio over network
            ok = send_audio(sock, data)
            data_queue.task_done()
            if ok == False:
                # Stop recording
                return
    except Empty as e:
        logging.info("Network thread timed out waiting for audio data. Closing socket!")
        sock.close()
    except ValueError as e:
        logging.info("Closing socket due to: %s", e)
        sock.close()
    finally:
        logging.info("Set recording to false")
        with lock:
            recording = False

def record_audio(audio: pyaudio.PyAudio, config: object):
    global recording
    global data_queue
    chunk = config.buffer
    audio_format = config.audio_format
    channels = config.channels
    rate = config.rate
    input_device = config.input
    logging.debug("Will start recording with parameters: chunk size %d, audio format %s, channels %d, rate %d, input device %d", chunk, config.format, channels, rate, input_device)
    with lock:
        recording = True
    stream = audio.open(format=audio_format,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk, 
                input_device_index=input_device)
    logging.info("Recording started...")
    stream.start_stream()
    # Record data until recording condition is true
    while True:
        with lock:
            if recording == False:
                logging.info("Will break recording loop")
                break
        data = stream.read(chunk, exception_on_overflow=False)
        try:
            data_queue.put_nowait(data)
        except Full as e:
            logging.warn("Audio queue is full, dropping frames...")
    # Stop recording and cleanup
    stream.stop_stream()
    stream.close()
    logging.info("Recording stopped...")

def handle_client(server: socket.socket, audio: pyaudio.PyAudio, config: object):
    sock, addr = server.accept()
    logging.info("Accepted connection from %s", addr)
    t = threading.Thread(target=process_audio, args=(sock,))
    t.start()
    record_audio(audio, config)
    t.join()
    logging.info("Finished handling client %s", addr)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='netmic')
    parser.add_argument('-i', '--input', type=int, nargs='?', help='the index of the input device (default is 0)', default=0)
    parser.add_argument('-p', '--port', type=int, help='the TCP port to listen on', default=8347)
    parser.add_argument('-f', '--format', type=str, help='the audio input format (supported formats are Float32, Int32, Int24, Int16, Int8, UInt8)', default='Int16')
    parser.add_argument('-r', '--rate', type=int, help='the sample rate', default=16000)
    parser.add_argument('-c', '--channels', type=int, help='the number of input channels (default is Mono)', default=1)
    parser.add_argument('-b', '--buffer', type=int, help='the audio buffer chunk size', default=2048)
    args = parser.parse_args()
    # Adjust format
    if args.format == 'Float32':
        args.audio_format = pyaudio.paFloat32
    elif args.format == 'Int32':
        args.audio_format = pyaudio.paInt32
    elif args.format == 'Int24':
        args.audio_format = pyaudio.paInt24
    elif args.format == 'Int16':
        args.audio_format = pyaudio.paInt16
    elif args.format == 'Int8':
        args.audio_format = pyaudio.paInt8
    elif args.format == 'UInt8':
        args.audio_format = pyaudio.paUInt8
    else:
        logging.warning("Invalid audio format specified: %s. Will use default format Int16", args.format)
        args.audio_format = pyaudio.paInt16
    return args

def main():
    global recording
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    audio = pyaudio.PyAudio()
    config = parse_args()
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(("0.0.0.0", config.port))
    serversocket.listen(1)
    logging.info("Network server started")
    try:
        while True:
            handle_client(serversocket, audio, config)
    except KeyboardInterrupt as e:
        logging.info("Keyboard interrupt received")
        with lock:
            recording = False
        sys.exit(1)
    finally:
        serversocket.close()
        audio.terminate()
        logging.info("Network server stopped")

if __name__ == "__main__":
    main()