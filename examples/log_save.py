# usage: python3 log_acc.py [mac]
from __future__ import print_function
from mbientlab.metawear import MetaWear, libmetawear, parse_value, create_voidp, create_voidp_int
from mbientlab.metawear.cbindings import *
from time import sleep
from threading import Event
from ctypes import c_void_p
from datetime import datetime



import sys
import time
import tkinter as tk
import pandas as pd
from glob import glob

# import for playing videos
import cv2
from ffpyplayer.player import MediaPlayer


# def path to vid
vid_path = 'C:\\Users\\arush\\Desktop\\Thesis\\Metaware_exp\\videos'

# define function to play video
def PlayVideo(video_path):
    video = cv2.VideoCapture(video_path)
    window_name = "window"
    player = MediaPlayer(video_path)

    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    while True:
        grabbed, frame = video.read()
        audio_frame, val = player.get_frame()
        if not grabbed:
            print("End of video")
            break
        if cv2.waitKey(28) & 0xFF == ord("q"):
            break
        cv2.imshow(window_name, frame)
        if val != 'eof' and audio_frame is not None:
            #audio
            img, t = audio_frame
    video.release()
    cv2.destroyAllWindows()


# select the first video
vid = glob(f'{vid_path}\*')[0]


# create GUI
root = tk.Tk()
root.title('Logger')
root.geometry("600x600")
label = tk.Label()
text = tk.Text(root, height = 30, width = 52)
btn_chk = tk.IntVar()
button = tk.Button(root, text ="start experiment", command = lambda: btn_chk.set(1))

label.pack()
text.pack()
button.pack()

def print(print_str):
    text.insert(tk.END, print_str+'\n')
    root.update()
print("Please wait, setting up experiment")

# print("Searching for device...")
d = MetaWear(sys.argv[1])  # D0:75:54:CD:1D:01
d.connect()
# print("Connected to " + d.address)


# print("Configuring device")

try:
    # print("Get and log acc signal")
    acc = libmetawear.mbl_mw_acc_get_acceleration_data_signal(d.board)
    gyro = libmetawear.mbl_mw_gyro_bmi270_get_packed_rotation_data_signal(d.board)

    logger_acc = create_voidp(lambda fn: libmetawear.mbl_mw_datasignal_log(acc, None, fn))
    logger_gyro = create_voidp(lambda fn: libmetawear.mbl_mw_datasignal_log(gyro, None, fn))
    
    # print("Start logging")
    libmetawear.mbl_mw_logging_start(d.board, 0)
    
    print("press start experiment")
    button.wait_variable(btn_chk)
    log_start_time = time.time()

    # print("Start acc and gyro")
    libmetawear.mbl_mw_gyro_bmi270_enable_rotation_sampling(d.board)
    libmetawear.mbl_mw_acc_enable_acceleration_sampling(d.board)
    libmetawear.mbl_mw_gyro_bmi270_start(d.board)
    libmetawear.mbl_mw_acc_start(d.board)

    # print("Logging data")
    PlayVideo(vid)
    log_end_time = time.time()
    print(f"data logged for {(log_end_time - log_start_time):.3f} s ")

    # print("Setup acc")
    libmetawear.mbl_mw_acc_stop(d.board)
    libmetawear.mbl_mw_acc_disable_acceleration_sampling(d.board)
    libmetawear.mbl_mw_gyro_bmi270_disable_rotation_sampling(d.board)
    
    # print("Stop logging")
    libmetawear.mbl_mw_logging_stop(d.board)

    # print("Flush cache if MMS")
    libmetawear.mbl_mw_logging_flush_page(d.board)
    
    # print("set connection parameters")
    libmetawear.mbl_mw_settings_set_connection_parameters(d.board, 7.5, 7.5, 0, 6000)
    sleep(1.0)

    # print("Setup Download handler")
    e = Event()
    def progress_update_handler(context, entries_left, total_entries):
        if (entries_left == 0):
            e.set()
    
    fn_wrapper = FnVoid_VoidP_UInt_UInt(progress_update_handler)
    download_handler = LogDownloadHandler(context = None, \
        received_progress_update = fn_wrapper, \
        received_unknown_entry = cast(None, FnVoid_VoidP_UByte_Long_UByteP_UByte), \
        received_unhandled_entry = cast(None, FnVoid_VoidP_DataP))

    logged_data = []
    def callback_fn(p, type_):
        values = parse_value(p, n_elem = 1)
        data_dict = {}

        data_dict['epoch'] = int(p.contents.epoch)
        data_dict[f'x_{type_}'] = float(values.x)
        data_dict[f'y_{type_}'] = float(values.y)
        data_dict[f'z_{type_}'] = float(values.z)

        logged_data.append(data_dict)
    callback_acc = FnVoid_VoidP_DataP(lambda ctx, p: callback_fn(p, 'acc'))
    callback_gyro = FnVoid_VoidP_DataP(lambda ctx, p: callback_fn(p, 'gyro'))
    
    # print("Subscribe to logger")
    libmetawear.mbl_mw_logger_subscribe(logger_acc, None, callback_acc)
    libmetawear.mbl_mw_logger_subscribe(logger_gyro, None, callback_gyro)
    
    print("Download data")
    libmetawear.mbl_mw_logging_download(d.board, 0, byref(download_handler))
    e.wait()

    fused_data = []
    for i, curr_dict in enumerate(logged_data[:-1]):
        curr_epoch = curr_dict['epoch']
        nxt_dict = logged_data[i+1]
        nxt_epoch = nxt_dict['epoch']
        if curr_epoch == nxt_epoch:
            if 'x_acc' in curr_dict and 'x_gyro' in nxt_dict:
                fused_dict = {**curr_dict, **nxt_dict}
            fused_data.append(fused_dict)

    # for log in fused_data: print(log)    # print list of dicts
    df = pd.DataFrame(fused_data)  # convert to dataframe
    # print(df)

    #creating time_stamp
    # Getting the current date and time
    dt = datetime.now()

    # getting the timestamp
    ts = datetime.timestamp(dt)

    print("Date and time is:", dt)
    print("Timestamp is:", ts)  


    print("Saving data as csv")
    df.to_csv('saved_data_'+str(ts)+'.csv')
	
except RuntimeError as err:
    print(err)
finally:
    # print("Resetting device")
    pass
    
    e = Event()
    d.on_disconnect = lambda status: e.set()
    # print("Debug reset")
    libmetawear.mbl_mw_debug_reset(d.board)
    e.wait()

print('Finished')
root.mainloop()