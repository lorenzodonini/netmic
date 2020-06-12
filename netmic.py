import socket
import pyaudio
import logging
import time
import threading
import sys
import wave
from queue import Queue, Empty, Full

lock = threading.Lock()
recording = False
data_queue = Queue(maxsize=20)

def send_audio(sock, data) -> bool:
    totalsent = 0
    data_len = len(data)
    logging.debug("Sending sampled %d audio bytes over network", data_len)
    while totalsent < data_len:
        sent = 0
        try:
            sent = sock.send(data[totalsent:])
            if sent == 0:
                logging.error("wtf1")
                raise RuntimeError("Socket connection broke")
        except Exception as err:
            logging.error("Error while sending audio data over network: %s", err)
            return False
        totalsent = totalsent + sent
    logging.debug("Sent %d bytes over network", data_len)
    return True

def process_audio(sock):
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

def record_audio(audio: pyaudio.PyAudio):
    global recording
    global data_queue
    CHUNK = 2048
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    with lock:
        recording = True
    stream = audio.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK, 
                input_device_index=0)
    logging.info("Recording started...")
    stream.start_stream()
    while True:
        with lock:
            if recording == False:
                logging.info("Will break recording loop")
                break
        data = stream.read(CHUNK, exception_on_overflow=False)
        try:
            data_queue.put_nowait(data)
        except Full as e:
            logging.warn("Audio queue is full, dropping frames...")
    stream.stop_stream()
    stream.close()
    logging.info("Recording stopped...")

def handle_client(server, audio):
    sock, addr = server.accept()
    logging.info("Accepted connection from %s", addr)
    t = threading.Thread(target=process_audio, args=(sock,))
    t.start()
    record_audio(audio)
    t.join()
    logging.info("Finished handling client %s", addr)

def main():
    global recording
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    audio = pyaudio.PyAudio()
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(("0.0.0.0", 13370))
    serversocket.listen(1)
    logging.info("Network server started")
    try:
        while True:
            handle_client(serversocket, audio)
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