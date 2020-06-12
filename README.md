# Network Microphone Streamer (netmic)

The script allows you to record audio from a microphone source and stream it (PCM) over the network to any other application, that requires audio input but doesn't have physical access to a microphone.

The following features are currently supported:
- one TCP client at a time
- PCM streaming
- customizable audio input format/rate

To request more features, please open an issue, or feel free to create a pull request.

## Setup

Pthon 3.6+ is required to run this script.

You will also need to install portaudio on your machine.

On macOS, run:
```
brew install portaudio
```

On Linux, run:
```
sudo apt install portaudio
```

Create a python virtual environment:
```
python3 -m venv env
source env/bin/activate
```

To install the dependencies, run:
```
pip install -r requirements.txt
```

### MacOS X

On macOS, you might have to install pyaudio with a tweak:
```
pip install --global-option='build_ext' --global-option='-I/usr/local/include' --global-option='-L/usr/local/lib' pyaudio
```

## Usage

Simply run:
```
python -u netmic.py
```

**NOTE: you may need to run the script with `sudo` for microphone access.**

The program waits until a client connects over TCP on port `8347`.

As soon as a connection is opened, it opens the microphone and starts streaming audio over the connection. Streaming will continue, until the TCP connection is closed.

Netmic uses a queue to buffer audio chunks, before sending them over the network.
If a client doesn't consume the network input quickly enough, eventually audio frames will be dropped.

