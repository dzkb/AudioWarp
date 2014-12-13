'''
Copyright (c) 2014 Dzakub

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

import pyaudio
import wave
import os
import threading
from ctypes import *
import ctypes.wintypes
import win32con
import sys
import time
import pydub

user32 = windll.user32

p = pyaudio.PyAudio()

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 5
TIME = 60 # total time
BUFFERS = int(TIME/RECORD_SECONDS) # amount of 5-seconds temporary buffer files
TMP_EXTENSION = ".tmp"
THREAD_COUNT = 2 # one for OS audio, one for the microphone

threads = dict()
mergingLock = threading.Lock()
merge_and_save = False
shallQuit = False
f_counters = dict() # contains buffer files counters
'''
    \/ - example f_counter
+--+--+--+--+--+
| 1| 2| 3| 4| 5|
+--+--+--+--+--+
'''

def mergeAndSave(counter, buffers, channels, iformat, rate, thread_id):
    print("[" + str(thread_id) + "] " + "counter is " + str(counter))
    print("[" + str(thread_id) + "] " + "counter - buffers is " + str(counter-buffers))

    wavedata = []
    for i in range(buffers-counter):
        filename = str(i+counter) + TMP_EXTENSION
        print("[" + str(thread_id) + "] " + "(1) merging file " + filename)
        if os.path.isfile(filename):
            f = wave.open(filename, "rb")
            wavedata.append(f.readframes(f.getnframes()))
            f.close()
    for i in range(counter):
        filename = str(i) + TMP_EXTENSION
        print("[" + str(thread_id) + "] " + " (2) merging file " + filename)
        if os.path.isfile(filename):
            f = wave.open(filename, "rb")
            wavedata.append(f.readframes(f.getnframes()))
            f.close()

    # outName = time.strftime("%Y-%m-%d_%Hh%Mm%Ss") + ".wav"
    outName = "out_" + str(thread_id)

    out = wave.open(outName, "wb")
    out.setnchannels(channels)
    out.setsampwidth(p.get_sample_size(iformat))
    out.setframerate(rate)
    out.writeframes(b''.join(wavedata))
    out.close()

def recordingThread(thread_id):
    global merge_and_save
    f_counter = 0

    for k,v in enumerate(p.get_device_info_by_index(2).items()):
        print (str(k) + ": " + str(v))

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=2)

    while not shallQuit:
        frames = []
        j = 0

        print ("[" + str(thread_id) + "] " + "Filling buffer #" + str(f_counter))

        while (j < int(RATE / CHUNK * RECORD_SECONDS)) and (not merge_and_save) :
            data = stream.read(CHUNK)
            frames.append(data)
            j += 1

        print("[" + str(thread_id) + "] " + "* done recording")

        wave_filename = str(f_counter)

        wf = wave.open(wave_filename + "_" + str(thread_id) + TMP_EXTENSION, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        if f_counter < BUFFERS-1:
            f_counter += 1
        else:
            f_counter = 0

        if merge_and_save:
            mergeAndSave(f_counter, BUFFERS, CHANNELS, FORMAT, RATE, thread_id)
            mergingLock.acquire()
            merge_and_save = False
            mergingLock.release()

    print("[" + str(thread_id) + "] " + "terminating...")
    stream.stop_stream()
    stream.close()

for i in range(THREAD_COUNT): # create one worker thread for every audio device
    t = threading.Thread(target=recordingThread, daemon=True, kwargs={'thread_id': i})
    t.start()
    threads[i] = t
    print ("Thread " + str(i) + " started")

def stopThat() :
    global shallQuit
    print("[MAIN] Requested stop")
    shallQuit = True
    for k, t in threads.items():
        t.join()
        print("[MAIN] Joining thread " + str(k))
    sys.exit(0)

def startMerging():
    print("[MAIN] Requested save")
    global merge_and_save
    mergingLock.acquire()
    merge_and_save = True
    mergingLock.release()

user32.RegisterHotKey(None, 1, win32con.MOD_WIN, win32con.VK_F3)
user32.RegisterHotKey(None, 2, win32con.MOD_WIN, win32con.VK_ESCAPE)

try:
    msg = ctypes.wintypes.MSG()
    while user32.GetMessageA(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == win32con.WM_HOTKEY:
            print("Received hotkey event " + str(msg.wParam))
            if msg.wParam == 1:
                startMerging()
            elif msg.wParam == 2:
                stopThat()

        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))
finally:
    user32.UnregisterHotKey(None, 1)
    user32.UnregisterHotKey(None, 2)