'''
:Date: 2018-03-07
:Version: 0.0.6
:Authors:
    - Mohammad Alghafli <thebsom@gmail.com>

Event driven http download library with automatic resume and other features.
The goal of this module is to ease the process of downloading files and resuming
interrupted downloads. The library is written in an event-driven style similar
to GTK. The module defines the class `Downloader`. Instances of this class
download a file from an http server and call callback functions whenever an
event happens ralated to this download. Examples of events are download state
change (start, pause, complete, error) and download speed change. The following
is a typical usage example::
    
    import bitpit
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    d = bitpit.Downloader(url) #downloader instance
    
    #listen to download events and call a function whenever an event happens
    #print state when state changes
    d.listen('state-changed', lambda var: print('download state:', var.state))
    
    #print speed in human readable format whenever speed changes
    #speed is updated and callback is called every 1 second by default
    d.listen('speed-changed', lambda var: print('download speed:', *var.human_speed))
    
    #register another callback function to the speed change signal
    #print percentage downloaded whenever speed changes
    d.listen('speed-changed', lambda var: print(int(var.percentage), '%'))
    
    #print total file size in human readable format when the downloader knows the file size
    d.listen('size-changed', lambda var: print('total file size:', *var.human_size))
    
    #done registering callbacks. lets start our download
    #the following call will not block. it will start a new download thread
    d.start()
    
    #do some other work while download is taking place...
    
    #wait for download completion or error
    d.join()

This module can also be run as a main python script to download a file. You can have a look at the main function for another usage example.

commandline syntax::

    python -m bitpit.py <url>
    
args:
    url: the url to download.
'''

import requests
import threading
import queue
import pathlib
import time
import datetime
import io
import sys
import traceback

__version__ = '0.0.6'

def human_readable(n, digits=3):
    '''
    return a human readable number of bytes
    args::
        n:      the number to return as human readable.
        digits: the number of digits before the decimal point. (default=3)
    returns::
        tuple:
            0: (float) human readable number or None if n is None.
            1: (str) suffix or None if n is None.
    '''
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    suffix = suffixes[0]
    for c in suffixes[1:]:
        if len(str(abs(int(n)))) > digits:
            n /= 1024
            suffix = c
    
    return n, suffix

class Emitter:
    '''
    a base class for classes that implement event driven programming. a derived class should define the class attribute `__signals__` which is a sequence of its valid signals.
    '''
    __signals__ = tuple()
    
    def __init__(self):
        self.listeners = {}
    
    def listen(self, signal, func):
        '''
        registers the callback function `func` for the signal `signal`. whenever the signal is emitted, the callback function will be called with 1 argument which is the object that emitted the signal. listening to a signal not present in class attribute `__signals__` raises `KeyError`. registering a callback function multiple times calls the function that number of times when the signal is emitted.
        args::
            signal: the signal to listen to.
            func: the callback function.
        returns::
            None.
        '''
        if signal not in type(self).__signals__:
            raise KeyError('unknown signal', signal)
        
        if signal not in self.listeners:
            self.listeners[signal] = []
        
        self.listeners[signal].append(func)
        
    def unlisten(self, signal, func):
        '''
        unregisters the callback function `func` for the signal `signal`. unlistening from an unknown signal raises `KeyError`. unlistening a callback which was not passed to `listen` method previously raises a `ValueError`. unlistening a call back will remove it from callback list only once. if the callback was passed to `self.listen()` multiple times, it must be unlistened that number of times to be completely removed from the callback list.
        args::
            signal: the signal to unlisten from.
            func: the callback function.
        returns::
            None.
        '''
        self.listeners[signal].remove(func)
    
    def emit(self, signal):
        '''
        calls all callback functions previously registered for the signal by calling `self.listen()`. emitting a signal not present in `__signals__` class property raises `KeyError`. exceptions raised by the callback function are printed to stderr and ignored.
        args::
            signal: the signal to call its callbacks
        returns::
            None.
        '''
        if signal not in type(self).__signals__:
            raise KeyError('unknown signal', signal)
        
        if signal in self.listeners:
            for c in self.listeners[signal]:
                try:
                    c(self)
                except Exception as e:
                    print(c.__name__, 'error:', type(e), e, file=sys.stderr)
                    print(traceback.format_exc())

class Downloader(Emitter):
    '''
    download manager class. instances of this class are able to download files from an http server in a dedicated thread, pause download and resume download. it subclasses class `Emitter` and defines 3 signals::
        state-changed::
            emitted when the state of the download is changed. there are 4 states: paused (not downloading), start (downloading now), error (same as pause but caused by an error) and complete (finished downloading). to know the current state, check attribute `self.state`.
        size-changed::
            emitted when the total file size is updated. this is done when the file size is retrieved from the http server and also after the file is completely retrieved from the server. to know the total file size, check attribute `self.size`.
        speed-changed::
            emitted periodically after the instance starts downloading. the period between 2 consecutive emissions of this signal is set in `self.__init__()`. this signal is also emitted whenever the state of the download changes just before state-changed signal is emitted. to know the current speed, check attribute `self.speed`.
        in addition to listen and unlisten, you probably want to usethe following methods::
            - `self.start()`
            - `self.stop()`
            - `self.join()`
            - `self.bar()`
    '''
    __signals__ = tuple(('state-changed', 'size-changed', 'speed-changed'))
    
    def __init__(self, url, path=None, restart_wait=-1, chunk_size=128*2**10, update_period=1, timeout=10, rate_limit=0):
        '''
        constructor for `Downloader`.
        args::
            url::
                the url to download.
            path::
                can be one of the following values::
                    - an instance of `io.BufferedIOBase` (opened binary file or `io.BytesIO`).
                    - a value that can be passed to `pathlib.Path` constructor. a file will be opened in the specified path and data will be downloaded to it.
                    - None. a new file whose name is equal to the last part of the url will be created in the current directory.
            restart_wait::
                if >= 0, the instance will wait this number of seconds before restarting download when an error occures. if < 0, the instance will not restart even after error. (default -1)
            chunk_size::
                the size of the data to read at each read operation from the network. (default 128 kb)
            update_period::
                the minimum time in seconds between 2 consecutive updates of the download speed and emission of speed-changed signal. the update will never happen before this number of seconds but it may happen after more than this number of seconds. (default 1)
            timeout::
                the timeout in seconds for reads from the network socket. (default 10)
            rate_limit::
                the download speed limit. if > 0, the downloader will limit the download speed to be close to this value. if <= 0, no speed limit and downloader will download as fast as possible. (default 0)
        returns::
           None.
        '''
        
        super().__init__()
        self._url = url
        if path is None:
            path = url.strip('/').split('/')[-1]
        if not isinstance(path, io.BufferedIOBase):
            self._path = pathlib.Path(path)
        else:
            self._path = path
        self.restart_wait = restart_wait
        self.chunk_size = chunk_size
        self.update_period = update_period
        self.timeout = timeout
        self.bytes_per_period = rate_limit * update_period
        self.lock = threading.Lock()
        self.thread = None
        self.restart_thread = None
        self.wait_queue = queue.Queue(10)
        self._size = -1
        self.set_downloaded(0)
        self._speed = 0
        self.last_speed_update = time.monotonic()
        self.last_speed_downloaded = 0
        self.last_exception = None
        
        #avoid long sleeps when chunk_size is higher than rate_limit.
        if rate_limit > 0:
            self.chunk_size = min(self.chunk_size, rate_limit)
        
        self.set_state('pause')
    
    def join(self, timeout=None):
        '''
        waits until the downloading thread terminates for any reason (download completion, error or pause). check `self.state` after join if you want to know the state of the download.
        args::
            timeout: the timeout for the join operation.
        returns::
            None.
        '''
        if self.is_alive:
            self.thread.join(timeout)
    
    def start(self):
        '''
        starts a downloading thread. if `self.path` is has data, the download will resume and bytes will be appended to the end of the file. does nothing if the downloader is already started. if there is a scheduled restart, it will be cancelled.
        args::
            None.
        returns::
            None.
        '''
        self.lock.acquire()
        if not self.is_alive:
            if self.restart_thread is not None and self.restart_thread.is_alive():
                try:
                    self.wait_queue.put_nowait(None)
                except queue.Full:
                    pass
            self.thread = threading.Thread(target=self.do_start)
            self.thread.start()
        self.lock.release()
    
    def do_start(self):
        '''
        downloading method. in this method the downloader actually downloads data. you should call `self.start()` instead.
        args::
            None.
        returns::
            None.
        '''
        try:
            try:
                while True:
                    self.wait_queue.get_nowait()
            except queue.Empty:
                pass
            
            close_f = False
            if isinstance(self.path, pathlib.Path):
                if self.path.exists():
                    self.set_downloaded(self.path.stat().st_size)
            else:
                self.set_downloaded(self.path.tell())
            
            range = 'bytes={}-'.format(self.downloaded)
            request = requests.get(self.url, headers={'Range': range}, stream=True, timeout=self.timeout)
            request.raise_for_status()
            
            if request.status_code == requests.codes.no_content:
                self.set_size(self.downloaded)
            else:
                if 'Content-Range' in request.headers:
                    content_range = request.headers['Content-Range'].split()
                    size = content_range[1].split('/')[1]
                    self.set_size(int(size))
                elif 'Content-Length' in request.headers:
                    self.set_size(self.downloaded + int(request.headers['Content-Length']))
                else:
                    self.set_size(-1)
            
            if isinstance(self.path, pathlib.Path):
                f = self.path.open('ba')
                close_f = True
            else:
                f = self.path
                close_f = False
            
            self.set_downloaded(f.tell())
            self.set_state('start')
            
            downloaded_this_period = 0
            for data in request.iter_content(chunk_size=self.chunk_size):
                t0 = time.monotonic()
                f.write(data)
                self.set_downloaded(f.tell())
                try:
                    self.wait_queue.get_nowait()
                    self.set_state('pause')
                    return
                except queue.Empty:
                    pass
                
                downloaded_this_period += len(data)
                if self.bytes_per_period > 0 and downloaded_this_period >= self.bytes_per_period:
                    wait = (self.update_period - t0 + self.last_speed_update) * downloaded_this_period / self.bytes_per_period
                    if wait > 0:
                        try:
                            self.wait_queue.get(timeout=wait)
                            self.set_state('pause')
                            return
                        except queue.Empty:
                            pass
                
                if time.monotonic() - self.last_speed_update > self.update_period:
                    self.update_speed()
                    downloaded_this_period = 0
            
            self.set_size(self.downloaded)
            self.set_state('complete')
        except Exception as e:
            try:
                self.wait_queue.get_nowait()
                self.set_state('pause')
            except queue.Empty:
                self.last_exception = e
                self.set_state('error')
        finally:
            if close_f:
                f.close()
        
        if self.state == 'error' and self.restart_wait >= 0:
            self.restart()
    
    def stop(self):
        '''
        stops downloading thread. does nothing if the downloader is already stopped. if there is a scheduled restart, it will be cancelled.
        args::
            None.
        returns::
            None.
        '''
        try:
            self.wait_queue.put_nowait(None)
        except queue.Full:
            pass
    
    def restart(self, wait=None):
        '''
        schedules a download restart and returns.
        args::
            wait: seconds to wait before the restart. if None, uses `self.restart_wait`. if `self.restart_wait` < 0, defaults to 30 seconds (default None)
        returns::
            None.
        '''
        self.restart_thread = threading.Thread(target=self.do_restart, args=(wait,))
        self.restart_thread.start()
    
    def do_restart(self, wait=None):
        '''
        waiting method before a restart. in this method actual waiting and restarting of the downloader happens. you should call `self.restart()` instead.
        args::
            wait: seconds to wait before the restart. if None, uses the `self.restart_wait`. if `self.restart_wait` < 0, defaults to 30 seconds (default None)
        returns::
            None.
        '''
        if wait is None:
            if self.restart_wait >= 0:
                wait = self.restart_wait
            else:
                wait = 30
        
        try:
            while True:
                self.wait_queue.get_nowait()
        except queue.Empty:
            pass
        
        try:
            self.wait_queue.get(timeout=wait)
        except queue.Empty:
            self.start()
    
    def set_state(self, value):
        '''
        sets the state of the downloader and emits speed-changed and state-changed signals. this method is for internal class use and you should not call it.
        '''
        self._speed = 0
        self.last_speed_update = time.monotonic()
        self._state = value
        self.emit('speed-changed')
        self.emit('state-changed')
    
    def set_size(self, value):
        '''
        sets the size of the downloader. this method is for internal class use and you should not call it.
        '''
        self._size = value
        self.emit('size-changed')
    
    def update_speed(self):
        '''
        recalculate download speed. you should not call this method. it is periodically called when the downloader starts.
        '''
        t = time.monotonic()
        d = self.downloaded
        dt = t - self.last_speed_update
        dd = d - self.last_speed_downloaded
        self.last_speed_update = t
        self.last_speed_downloaded = d
        if dt == 0:
            self._speed = 0
        else:
            self._speed = dd / dt
        
        self.emit('speed-changed')
    
    def bar(self, width=30, char='='):
        '''
        returns a string of width `width` representing a progress bar. the string is filled with `char` and spaces. the number of `char` represents the part of the file downloaded (e.g., if half of the file is downloaded, half of the string will be filled with `char`). the rest of the string will be filled with spaces. if the ratio of downloaded data is not known, returns a string of width `width` with the string "None" centered.
        '''
        if self.ratio >= 0:
            return (int(width * self.ratio) * char).ljust(width)
        else:
            return str(None).center(width)
    
    @property
    def is_alive(self):
        '''
        returns True if an active downloading thread exists. False otherwise.
        '''
        if self.thread is not None:
            return self.thread.is_alive()
        else:
            return False
    
    @property
    def state(self):
        '''
        current state of the downloader. there are 4 states defined::
            - start: the download is in progress now.
            - pause: the download is suspended using `self.stop()`.
            - error: the download is suspended due to an error.
            - complete: the download is completed.
        '''
        return self._state
    
    @property
    def size(self):
        '''
        size of the file to download. -1 if size is not known.
        '''
        return self._size
    
    @property
    def human_size(self):
        '''
        size of the file to download as a human readable value.
        returns::
            tuple:
                0: (float) human readable size between 0 and 1000 (1000 not included).
                1: (str) human readable suffix (KB for kilobytes, MB for megabytes...etc).
        '''
        return human_readable(self.size)
    
    @property
    def url(self):
        '''
        url to download.
        '''
        return self._url
    
    @property
    def path(self):
        '''
        path to download into. either a `pathlib.Path` object or an `io.BufferedIO` object.
        '''
        return self._path
    
    @property
    def ratio(self):
        '''
        ratio of downloaded data to the total size of the file as a float between 0 and 1 or -1.0 if ratio is not known.
        '''
        if self.size == 0:
            return 1.0
        elif self.size > 0:
            return self.downloaded / self.size
        else:
            return -1.0
    
    @property
    def percentage(self):
        '''
        ratio of downloaded data to the total size of the file as a float between 0 and 100 or -100 if percentage is not known.
        '''
        return 100 * self.ratio
    
    @property
    def downloaded(self):
        '''
        the number of downloaded bytes.
        '''
        return self._downloaded
    
    @property
    def human_downloaded(self):
        '''
        the number of downloaded bytes as a human readable value.
        returns::
            tuple:
                0: (float) human readable number of bytes between 0 and 1000 (1000 not included).
                1: (str) human readable suffix (KB for kilobytes, MB for megabytes...etc).
        '''
        return human_readable(self.downloaded)
    
    def set_downloaded(self, value):
        '''
        sets the number of downloaded bytes. this method is for internal class use and you should not call it.
        '''
        self._downloaded = value
    
    @property
    def remaining(self):
        '''
        the number of remaining bytes to download. -1 if not known.
        '''
        if self.size >= 0:
            return self.size - self.downloaded
        else:
            return -1
    
    @property
    def human_remaining(self):
        '''
        the number of remaining bytes to download as a human readable value.
        returns::
            tuple:
                0: (float) human readable number of bytes between 0 and 1000 (1000 not included).
                1: (str) human readable suffix (KB for kilobytes, MB for megabytes...etc).
        '''
        return human_readable(self.remaining)
    
    @property
    def speed(self):
        '''
        current download speed.
        '''
        return self._speed
    
    @property
    def human_speed(self):
        '''
        current download speed as a human readable value.
        returns::
            tuple:
                0: (float) human readable speed between 0 and 1000 (1000 not included).
                1: (str) human readable suffix (KB/s for kilobytes per second, MB/s for megabytes per second...etc).
        '''
        value = human_readable(self.speed)
        return value[0], value[1] + '/s'
    
    @property
    def eta(self):
        '''
        estimated time remaining to finish downloading the file. a `datetime.timedelta` object or None if not known.
        '''
        if self.remaining <= 0:
            return datetime.timedelta(seconds=0)
        elif self.speed == 0:
            return None
        else:
            return datetime.timedelta(seconds=self.remaining/self.speed)

def main(url):
    '''
    called when running this module as the main script. downloads the given url
    until done. on error, restarts after 30 seconds. displays a progress bar
    indicating how much of the file has been downloaded in addition to other
    statistics.
    args::
        url: the url to download.
    returns::
        None.
    '''
    def on_change(d):
        bar = d.bar(20)
        eta = d.eta
        if eta is not None:
            eta = datetime.timedelta(seconds=int(eta.total_seconds()))
        
        print('\r{0} | {1[0]:.2f} {1[1]} | {2[0]:.2f} {2[1]} | [{3}] {4:2.2f}% | {5}'.format(d.state, d.human_speed, d.human_downloaded, bar, d.percentage, eta).ljust(79), end='', flush=True)
    
    def wait_func(d):
        while True:
            try:
                input()
            except KeyboardInterrupt:
                d.stop()
                break
            except Exception:
                pass
    
    d = Downloader(url, restart_wait=30)
    d.listen('state-changed', on_change)
    d.listen('speed-changed', on_change)
    d.listen('size-changed', on_change)
    d.start()
    
    threading.Thread(target=wait_func, args=(d,), daemon=True).start()

if __name__ == '__main__':
    main(sys.argv[1])

