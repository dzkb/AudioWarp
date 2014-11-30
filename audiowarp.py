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
import pythoncom
import threading
from ctypes import *
import ctypes.wintypes
import win32con
import sys
import time

user32 = windll.user32

p = pyaudio.PyAudio()

mergingLock = threading.Lock()
merge_and_save = False
shallQuit = False

def mergeAndSave(counter, buffers, channels, iformat, rate):
    print("counter is " + str(counter))
    print("counter - buffers is " + str(counter-buffers))

    wavedata = []
    for i in range(buffers-counter):
        print("(1) merging file " + str(i+counter))
        if os.path.isfile(str(i+counter)):
            f = wave.open(str(i+counter), "rb")
            wavedata.append(f.readframes(f.getnframes()))
            f.close()
    for i in range(counter):
        print("(2) merging file " + str(i))
        if os.path.isfile(str(i)):
            f = wave.open(str(i), "rb")
            wavedata.append(f.readframes(f.getnframes()))
            f.close()

    # for i in range(buffers):
    #     if (i + counter) < buffers:
    #         if os.path.isfile(str(i+counter)):
    #             f = wave.open(str(i+counter), "rb")
    #             wavedata.append(f.readframes(f.getnframes()))
    #             f.close()
    #     else:
    #         if os.path.isfile(str(i+counter)):

    outName = time.strftime("%Y-%m-%d_%Hh%Mm%Ss") + ".wav"

    out = wave.open(outName, "wb")
    out.setnchannels(channels)
    out.setsampwidth(p.get_sample_size(iformat))
    out.setframerate(rate)
    out.writeframes(b''.join(wavedata))    

def recordingThread():
    global merge_and_save
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 5
    TIME = 60 # total time
    BUFFERS = int(TIME/RECORD_SECONDS) # amount of 5-seconds temporary buffer files
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

        print ("Filling buffer #" + str(f_counter))

        while (j < int(RATE / CHUNK * RECORD_SECONDS)) and (not merge_and_save) :
            data = stream.read(CHUNK)
            frames.append(data)
            j += 1

        print("* done recording")

        wave_filename = str(f_counter)

        wf = wave.open(wave_filename, 'wb')
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
            mergeAndSave(f_counter, BUFFERS, CHANNELS, FORMAT, RATE)
            mergingLock.acquire()
            merge_and_save = False
            mergingLock.release()

    print("terminating...")        
    stream.stop_stream()
    stream.close()


t = threading.Thread(target=recordingThread, daemon=True)
t.start()

def stopThat() :
    global shallQuit
    print("Requested stop")
    shallQuit = True
    t.join()
    sys.exit(0)

def startMerging():
    print("Requested save")
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
            print("Received hotkey event " + msg.wParam)
            if msg.wParam == 1:
                startMerging()
            elif msg.wParam == 2:
                stopThat()

        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageA(ctypes.byref(msg))
finally:
    user32.UnregisterHotKey(None, 1)
    user32.UnregisterHotKey(None, 2)