from math import floor
import cv2
import tkinter as TK
import PIL.Image, PIL.ImageTk
import threading
import platform

from config import SOURCES
# # RTSP
# SOURCES = {
#     'url' : 'rtsp://{user}:{password}@{host}:{port}/ISAPI/Streaming/Channels/{channel}',
#     'login' : 'login',
#     'password' : 'password',
#     'port' : 554,
#     'subchannel' : 2,
#     'getChannel' : (lambda ch, sch : ('{}0{}' if len(str(ch)) == 1 else '{}{}').format(ch, sch)),
#     'sources' : [
#         {
#             'host' : '127.0.0.1',
#             'channels' : [1, 2, 4, 5, 9],
#         },
#         {
#             'host' : '127.0.0.1',
#             'channels' : [1, 2, 4],
#         },
#     ]
# }
# ##


class VideoStream(threading.Thread):
    def __init__(self, source, id) -> None:
        super().__init__()
        self.id = id
        self.source = source
        self.width = 0
        self.height = 0
        self.stopped = True
        self.ret = False
        self.frame = None
        self.error_counter = 0
        self.cap = None

    def log(self, text):
        print("Stream ID={}: {}".format(self.id, text))

    def getFrame(self, width=None, height=None):
        if not self.is_alive():
            self.log('not alive, start')
            self.start()

        if self.frame is not None:
            if width is not None or height is not None:
                orig_height, orig_width = self.frame.shape[:2]
                dsize : cv2.typing.Size = (orig_width if width is None else width, orig_height if height is None else height)
                return self.ret, cv2.resize(self.frame, dsize)
        return self.ret, self.frame

    def _stop(self, wait=True):
        self.stopped = True
        if wait == True:
            while self.is_alive():
                pass

    def _open(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.source)
        else:
            self.cap.open(self.source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        self.width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    def _release(self):
        if self.cap is not None:
            if self.cap.isOpened():
                self.cap.release()

    def _reopen(self):
        self._release()
        self._open()

    def run(self):
        self.stopped = False
        self.log("graber started")
        while(not self.stopped):
            if self.cap is None:
                self.log('Open from source')
                self._open()

            if not self.cap.isOpened():
                self.log('not opened, open')
                self._open()

            if self.error_counter > 10:
                self.log('error, trying reopen')
                self._reopen()

            if self.cap.isOpened():
                self.ret, self.frame = self.cap.read()
                if self.ret:
                    self.error_counter = 0
                else:
                    self.error_counter += 1
        self.log('graber stopped')

    def __del__(self):
        self._stop()
        self._release()
        self.log('destroyed')

class VideoCanvas:
    
    counter = 0

    @classmethod
    def getId(cls):
        cls.counter += 1
        return cls.counter

    def __init__(self, parent, source, grid_row=0, grid_col=0, width=320, height=240, connect=True):
        self.parent = parent
        self.photo = None

        self.width = width
        self.height = height

        self.source = source
        self.video_source = None

        print('w={}, h={}'.format(self.width, self.height))
        
        if connect == True:
            self._connect()

        self.canvas = TK.Canvas(parent, width=self.width, height=self.height, borderwidth=0, background='#000000', highlightthickness=0)
        self.canvas.grid(row=grid_row, column=grid_col)

    def __del__(self):
        self._disconnect()
        self.canvas.destroy()

    def _connect(self):
        if self.video_source is None:
            self.video_source = VideoStream(self.source, __class__.getId())
            self.video_source.start()
        

    def _disconnect(self):
        if self.video_source is not None:
            del self.video_source
            self.video_source = None

    def setGrid(self, grid_row=0, grid_col=0):
        self.canvas.grid(row=grid_row, column=grid_col, padx=0, pady=0, ipadx=0, ipady=0, sticky='nw')

    def setSize(self, width, height):
        self.width = width
        self.height = height
        self.canvas.configure(width=self.width, height=self.height)

    def update(self):

        if self.video_source is None:
            self._connect()
            return

        ret, frame = self.video_source.getFrame(self.width, self.height)

        #print(ret, frame)
        if ret:
            self.photo = PIL.ImageTk.PhotoImage(image = PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            self.canvas.create_image(0, 0, image = self.photo, anchor = TK.NW)
            #self.canvas.update()
        else:
            self.canvas.create_rectangle(0, 0, self.width, self.height, fill="#000000")
            self.canvas.create_text(self.width /2, self.height / 2, text="NO VIDEO", fill="#004D40")
            #print('no video')


class App:
    def __init__(self, window, title='App') -> None:
        self.window : TK.Tk = window
        self.window.title(title)
        if platform.system() == 'Windows':
            self.window.state('zoomed')
        else:
            self.window.attributes('-zoomed', True)
        self.window.protocol("WM_DELETE_WINDOW", self.onWindowClose)
        self.window.configure(padx=0, pady=0, bd=0)
        self.canvases = []
        self.delay = 10
        self.rows = 1
        self.columns = 1

        self.initialized = False

        self.screen_width = self.window.winfo_screenwidth()
        self.screen_height = self.window.winfo_screenheight()

        print('sw={}, sh={}, ww={}, wh={}', self.screen_width, self.screen_height, self.window.winfo_width(), self.window.winfo_height())

    def __del__(self):
        print("app destroyed")

    def buildURL(self, source: dict, defaults: dict, channel):
        tmpl = source.get('url', defaults.get('url'))
        ch = source.get('getChannel', defaults.get('getChannel'))(channel, source.get('subchannel', defaults.get('subchannel')))
        url = tmpl.format(
            user=source.get('login', defaults.get('login')),
            password=source.get('password', defaults.get('password')),
            host=source.get('host', defaults.get('host')),
            port=source.get('port', defaults.get('port')),
            channel=ch
        )
        return url

    def onWindowClose(self):
        print('window close')
        while len(self.canvases):
            cnv = self.canvases.pop()
            del cnv
        self.window.destroy()
        quit(0)

    def addChannel(self, source):
        cnv = VideoCanvas(self.window, source, connect=False)
        self.canvases.append(cnv)
        if len(self.canvases) < 3:
            self.rows = 1
            self.columns = 2
        elif len(self.canvases) < 5:
            self.rows = 2
            self.columns = 2
        elif len(self.canvases) < 7:
            self.rows = 3
            self.columns = 2
        elif len(self.canvases) < 10:
            self.rows = 3
            self.columns = 3
        
        r = 0
        c = 0
        for cnv in self.canvases:
            cnv.setGrid(r, c)
            c += 1
            if c >= self.columns:
                c = 0
                r += 1

        cnv_width = floor(self.window.winfo_width() / self.rows)
        cnv_height = floor(self.window.winfo_height() / self.columns)
        for cnv in self.canvases:
            cnv.setSize(cnv_width, cnv_height)
        print('ww={}, wh={}', self.window.winfo_width(), self.window.winfo_height())

                
    def run(self):
        self.update()
        self.window.mainloop()

    def update(self):
        #print(wnd_state)
        if not self.initialized:
            if self.window.winfo_viewable() == 1:
                for source in SOURCES['sources']:
                    for channel in source['channels']:
                        url = self.buildURL(source, SOURCES, channel)
                        print('Try open {}'.format(url))
                        app.addChannel(url)
                self.initialized = True
        else:                
            for canvas in self.canvases:
                canvas.update()

        self.window.after(self.delay, self.update)

if __name__ == '__main__':
    app = App(TK.Tk(), 'App')

    app.run()

