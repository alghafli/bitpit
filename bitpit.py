'''
:Date: 2019-10-13
:Version: 1.2.0
:Authors:
    * Mohammad Alghafli <thebsom@gmail.com>

Event driven http download library with automatic resume and other features.
The goal of this module is to ease the process of downloading files and resuming
interrupted downloads. The library is written in an event-driven style similar
to GTK. The module defines the class ``Downloader``. Instances of this class
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

This module can also be run as a main python script to download a file. You can
have a look at the main function for another usage example.

commandline syntax::

    python -m bitpit.py [-r rate_limit] [-m max_running] url [url ...]
    
args:
    * url: one or more urls to download.
    * -r rate_limit: total rate limit for all running downloads.
    * -m max_running: maximum number of running downloads at any single time.
'''

import requests
import urllib.parse
import threading
import queue
import pathlib
import time
import datetime
import io
import sys
import traceback
import re

__version__ = re.search(
        ':Version: (?P<version>[0-9](\.[0-9])*)',
        __doc__
    ).group(1)

def human_readable(n, digits=3):
    '''
    return a human readable number of bytes.
    
    args:
        * n (float): the number to return as human readable.
        * digits (int): the number of digits before the decimal point.
        
    returns:
        tuple:
            0. (float) human readable number or None if n is None.
            #. (str) suffix or None if n is None.
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
    a base class for classes that implement event driven programming. a derived
    class should define the class attribute ``__signals__`` which is a sequence of
    its valid signals.
    '''
    __signals__ = tuple()
    
    def __init__(self):
        self.listeners = {}
    
    def listen(self, signal, func, *args, **kwargs):
        '''
        registers the callback function ``func`` for the signal ``signal``. whenever
        the signal is emitted, the callback function will be called with 1
        argument which is the object that emitted the signal. listening to a
        signal not present in class attribute ``__signals__`` raises ``KeyError``.
        registering a callback function multiple times calls the function that
        number of times when the signal is emitted.
        
        args:
            * signal (str): the signal to listen to.
            * func (a callable): the callback function.
            * args: positional arguments to be passed to the callback.
            * kwargs: keyword arguments to be passed to the callback.
        '''
        if signal not in type(self).__signals__:
            raise KeyError('unknown signal', signal)
        
        if signal not in self.listeners:
            self.listeners[signal] = []
        
        self.listeners[signal].append((func, args, kwargs))
        
    def unlisten(self, signal, func, *args, **kwargs):
        '''
        unregisters the callback function ``func`` for the signal ``signal``.
        unlistening from an unknown signal raises ``KeyError``. unlistening a
        callback which was not passed to ``listen`` method previously raises a
        ``ValueError``. unlistening a call back will remove it from callback list
        only once. if the callback was passed to ``self.listen()`` multiple times,
        it must be unlistened that number of times to be completely removed from
        the callback list.
        
        args:
            * signal (str): the signal to unlisten from.
            * func (a callable): the callback function.
            * args: ``args`` that were passed to ``self.listen()``.
            * kwargs: ``kwargs`` that were passed to ``self.listen()``.
        '''
        self.listeners[signal].remove((func, args, kwargs))
    
    def emit(self, signal, *args):
        '''
        calls all callback functions previously registered for the signal by
        previous calls to ``self.listen()``. emitting a signal not present
        in ``__signals__`` class property raises ``KeyError``. exceptions raised by
        the callback function are printed to stderr and ignored.
        
        args:
            * signal (str): the signal to call its callbacks.
            * args: positional arguments to be passed to the callbacks. args
                that were passed to ``self.listen()`` will be after ``args`` that
                are passed to this method.
        '''
        if signal not in type(self).__signals__:
            raise KeyError('unknown signal', signal)
        
        if signal in self.listeners:
            for c in self.listeners[signal]:
                try:
                    c[0](*(args + c[1]), **c[2])
                except Exception as e:
                    print(file=sys.stderr)
                    print(
                            '{} error: {} {}'.format(
                                    c[0].__name__,
                                    type(e),
                                    e
                                ),
                            '{:-^79}'.format('trace'),
                            traceback.format_exc(),
                            '-'*79,
                            sep='\n',
                            file=sys.stderr
                        )

class Downloader(Emitter):
    '''
    downloader class. instances of this class are able to download files from an
    http or https server in a dedicated thread, pause download and resume
    download. it subclasses ``Emitter``.
    
    in addition to listen and unlisten, you probably want to use the
    following methods:
    
        * ``self.start()``
        * ``self.stop()``
        * ``self.join()``
        * ``self.bar()``
    
    properties:
    
    ================  ====================  =========  ========================
    name              type                  access     description
    ================  ====================  =========  ========================
    url               `str`                 RW         url to download. cannot
                                                       be set if `is_alive` is
                                                       True.
    path              `pathlib.Path` or     RW         path to download at. if
                      `io.BufferedIOBase`              an instance of
                                                       `pathlib.Path`, file
                                                       will be opened and
                                                       content will be written
                                                       to it. the file is
                                                       closed whenever the
                                                       download stops
                                                       (completion, pause or
                                                       error). if it is an
                                                       instance of
                                                       `io.BufferedIOBase`,
                                                       content is written to
                                                       the object and the
                                                       object is never closed.
                                                       cannot be set if
                                                       `is_alive` property is
                                                       True.
    restart_wait      `int`                 RW         number of seconds to
                                                       wait before restarting
                                                       the download in case of
                                                       error. setting it when
                                                       a restart thread is
                                                       active will restart the
                                                       thread again.
    restart_time      `datetime.datetime`   R          the time when the
                      or `None`                        download will be
                                                       restarted. `None` if
                                                       there is no scheduled
                                                       restart.
    chunk_size        `int`                 RW         number of bytes to write
                                                       in a single write
                                                       operation. ok to keep
                                                       default value. when set,
                                                       new value takes effect
                                                       in the next time the
                                                       download is started.
    update_period     `int`                 RW         `speed-changed` signal
                                                       is emitted every this
                                                       number of seconds.
    timeout           `int`                 RW         download will interrupt
                                                       when no bytes are
                                                       recieved for this number
                                                       of seconds. when set,
                                                       new value takes effect
                                                       in the next time the
                                                       download is started.
    rate_limit        `int`                 RW         speed limit of the
                                                       downloads in bytes per
                                                       second. may not work well
                                                       with small files.
    human_rate_limit  `tuple`               R          same as `rate_limit` but
                                                       as human readable tuple.
                                                       eg. (100.0, 'KB/s').
    size              `int`                 R          total size of the file
                                                       being downloaded in
                                                       bytes. -1 if unknown.
    human_size        `tuple`               R          same as `size` but as
                                                       human readable tuple.
    downloaded        `int`                 R          bytes downloaded so far.
    human_downloaded  `tuple`               R          same as `downloaded` but
                                                       as human readable tuple.
    remaining         `int`                 R          bytes remaining to
                                                       complete the download.
    human_remaining   `tuple`               R          same as `remaining` but
                                                       as human readable tuple.
    speed             `int`                 R          download speed in bytes
                                                       per second.
    human_speed       `tuple`               R          same as `speed` but as
                                                       human readable tuple.
    ratio             `float`               R          `downloaded` / `size`.
                                                       -1.0 if unknown.
    percentage        `float`               R          100 * `ratio`
    eta               `datetime.timedelta`  R          estimated time remaining
                                                       to complete the
                                                       download.
    state             `str`                 R          one of the following:
                                                        * start: trying to
                                                          connect.
                                                        * download:
                                                          downloading now.
                                                        * pause: stopped.
                                                        * error: stopped
                                                          because of an error.
                                                        * complete: completed.
    is_alive          `bool`                R          True if download thread
                                                       is running. False
                                                       otherwise.
    is_restarting     `bool`                R          True if restart thread
                                                       is running. False
                                                       otherwise.
    last_exception    `BaseException` or    R          last exception that
                      `None`                           occured during download.
                                                       `None` if no exception
                                                       occured yet.
    ================  ====================  =========  ========================
    
    signals:
        * state-changed: emitted when ``state`` property changes. its callback
            takes 2 positional arguments, the ``Downloader`` instance which
            emitted the signal and the old state the ``Downloader`` was in.
        * size-changed: emitted when ``size`` property changes. its callback takes
            1 positional argument, the ``Downloader`` instance which emitted the
            signal.
        * speed-changed: emitted when ``speed`` property changes. its callback
            takes 1 positional argument, the ``Downloader`` instance which emitted
            the signal.
        * url-changed: emitted when ``url`` property changes. its callback takes 1
            positional argument, the ``Downloader`` instance which emitted the
            signal.
        * path-changed: emitted when ``path`` property changes. its callback takes
            1 positional argument, the ``Downloader`` instance which emitted the
            signal.
        * restart-time-changed: emitted when ``restart_time`` property changes.
            its callback takes 1 positional argument, the ``Downloader`` instance
            which emitted the signal.
        * rate-limit-changed: emitted when ``rate_limit`` property changes. its
            callback takes 1 positional argument, the ``Downloader`` instance
            which emitted the signal.
    
    '''
    
    __signals__ = (
            'state-changed',
            'size-changed',
            'speed-changed',
            'url-changed',
            'path-changed',
            'restart-time-changed',
            'rate-limit-changed',
        )
    
    __non_fatal_errors__ = [408, 409, 500, 503, 504, ]
    
    def __init__(self, url, path=None, dir_path=False, rate_limit=0, timeout=10, update_period=1, restart_wait=-1, chunk_size=4*2**10):
        '''
        args:
         * url (str): sets ``url`` property.
         * path (any type that pathlib.Path constructor takes, ``io.BufferedIOBase``
            or ``None``): sets ``path`` property. ``None`` is the same as '.' and
            ``dir_path`` argument is ``True``.
         * dir_path (bool): if True, ``path`` argument is considered a directory and
            the file is saved in it. file name is taken from the url. ignored if
            ``path`` is ``None`` or instance of ``io.BufferedIOBase``.
         * rate_limit (int): sets ``rate_limit`` property.
         * timeout (float): sets ``timeout`` property.
         * update_period (float): sets ``update_period`` property.
         * restart_wait (float): sets ``restart_wait`` property.
         * chunk_size (int): sets ``chunk_size`` property.
        '''
        
        super().__init__()
        
        self._thread = threading.Thread(target=self._do_start)
        self._restart_thread = threading.Timer(0, self.start)
        self._lock = threading.RLock()
        
        self.url = url
        if path is None:
            path = '.'
            dir_path = True
        if isinstance(path, str):
            path = pathlib.Path(path)
        if isinstance(path, pathlib.Path) and dir_path:
            fname = urllib.parse.urlparse(url).path
            fname = urllib.parse.unquote(fname)
            fname = pathlib.Path(fname).name
            path = path / fname
        self.path = path
        self.restart_wait = restart_wait
        self._bytes_per_period = rate_limit * update_period
        self.chunk_size = chunk_size
        self._update_period = update_period
        self.timeout = timeout
        self._state = 'pause'
        self._q = queue.Queue()
        self._size = -1
        self._downloaded = 0
        self._speed = 0
        self._restart_time = None
        self.last_speed_update = time.monotonic()
        self.last_speed_downloaded = 0
        self._last_exception = None
    
    def join(self, timeout=None):
        '''
        waits until the downloading thread terminates for any reason (download
        completion, error or pause). check ``self.state`` after join if you want
        to know the state of the download.
        
        args:
            * timeout (None or int) the timeout for the join operation. defaults
                to None meaning no timeout.
        '''
        if self.is_alive:
            self._thread.join(timeout)
    
    def start(self):
        '''
        starts a downloading thread. if ``self.path`` has data, the download will
        resume and bytes will be appended to the end of the file. does nothing
        if the downloader is already started. if there is a scheduled restart,
        it will be cancelled.
        '''
        with self._lock:
            if not self.is_alive:
                self._restart_thread.cancel()
                self._thread = threading.Thread(target=self._do_start)
                self._thread.start()
    
    def _do_start(self):
        '''
        downloading method. in this method the downloader actually downloads
        data. you should call ``self.start()`` instead.
        '''
        try:
            self._set_restart_time(None)
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass
            
            self._set_state('start')
            
            close_f = False
            if isinstance(self.path, pathlib.Path):
                if self.path.exists():
                    self._set_downloaded(self.path.stat().st_size)
                else:
                    self._set_downloaded(0)
            else:
                self._set_downloaded(self.path.tell())
            
            self.update_size()
            if self.size > -1 and self.downloaded >= self.size:
                self._set_state('complete')
                return
            else:
                range = 'bytes={}-'.format(self.downloaded)
                request = requests.get(self.url, headers={'Range': range}, stream=True, timeout=self.timeout)
            
            completed_response = requests.codes.requested_range_not_satisfiable
            if request.status_code == completed_response:
                if 'Content-Range' in request.headers:
                    content_range = request.headers['Content-Range'].split()
                    size = content_range[1].split('/')[1]
                    self._set_size(int(size))
                
                if self.downloaded == self.size:
                    self._set_state('complete')
                    return
                else:
                    request.raise_for_status()
            else:
                request.raise_for_status()
                if 'Content-Range' in request.headers:
                    content_range = request.headers['Content-Range'].split()
                    size = content_range[1].split('/')[1]
                    self._set_size(int(size))
                elif 'Content-Length' in request.headers:
                    self._set_size(self.downloaded + int(request.headers['Content-Length']))
                else:
                    self._set_size(-1)
            
            if isinstance(self.path, pathlib.Path):
                f = self.path.open('ba')
                close_f = True
            else:
                f = self.path
            
            self._set_downloaded(f.tell())
            self._set_state('download')
            self._speed = 0
            self.last_speed_downloaded = 0
            
            downloaded_this_period = 0
            for data in request.iter_content(chunk_size=self.chunk_size):
                t0 = time.monotonic()
                f.write(data)
                self._set_downloaded(f.tell())
                try:
                    self._q.get_nowait()
                    self._set_state('pause')
                    return
                except queue.Empty:
                    pass
                
                downloaded_this_period += len(data)
                if self._bytes_per_period > 0 and downloaded_this_period >= self._bytes_per_period:
                    wait = (self.update_period - t0 + self.last_speed_update) * downloaded_this_period / self._bytes_per_period
                    if wait > 0:
                        try:
                            self._q.get(timeout=wait)
                            self._set_state('pause')
                            return
                        except queue.Empty:
                            pass
                
                if time.monotonic() - self.last_speed_update > self.update_period:
                    self._update_speed()
                    downloaded_this_period = 0
            
            self._set_size(self.downloaded)
            self._set_state('complete')
        except Exception as e:
            try:
                self._q.get_nowait()
                self._set_state('pause')
            except queue.Empty:
                self._last_exception = e
                if (
                        type(e) is requests.exceptions.HTTPError and
                        e.response.status_code not in self.__non_fatal_errors__
                    ):
                    self._set_state('fatal-error')
                else:
                    self._set_state('error')
        finally:
            if close_f:
                f.close()
            if self.state == 'error' and self.restart_wait >= 0:
                self.restart()
    
    def stop(self):
        '''
        stops downloading thread. does nothing if the downloader is already
        stopped. if there is a scheduled restart, it will be cancelled.
        '''
        self._restart_thread.cancel()
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
    
    def restart(self, wait=None):
        '''
        schedules a download restart and returns. it is called when an error
        occures during download and ``self.restart_wait`` property >= 0.
        
        args:
            * wait (float or None): seconds to wait before the restart. if None,
                uses ``self.restart_wait``.
        '''
        with self._lock:
            self._restart_thread.cancel()
            if wait is None:
                wait = self.restart_wait
            
            self._set_restart_time(
                    datetime.datetime.now() +
                    datetime.timedelta(seconds=wait)
                )
            self._restart_thread = threading.Timer(wait, self.start)
            self._restart_thread.start()
    
    def _do_restart(self, wait=None):
        '''
        waiting method before a restart. in this method actual waiting and
        restarting of the downloader happens. you should call ``self.restart()``
        instead.
        
        args:
            * wait (float or None): seconds to wait before the restart. if None,
                uses ``self.restart_wait``.
        '''
        if wait is None:
            if self.restart_wait >= 0:
                wait = self.restart_wait
            else:
                wait = 30
        
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        
        if not self.is_alive:
            try:
                self._set_restart_time(datetime.datetime.now() + datetime.timedelta(seconds=wait))
                self._q.get(timeout=wait)
            except queue.Empty:
                self._set_restart_time(None)
                self.start()
    
    def _set_state(self, value):
        '''
        sets the state of the downloader and emits speed-changed and
        state-changed signals. this method is for internal class use and you
        should not call it.
        '''
        old_state = self.state
        self._speed = 0
        self.last_speed_update = time.monotonic()
        self._state = value
        self.emit('speed-changed', self)
        self.emit('state-changed', self, old_state)
    
    def _set_size(self, value):
        '''
        sets the size of the downloader. this method is for internal class use
        and you should not call it.
        '''
        if value != self._size:
            self._size = value
            self.emit('size-changed', self)
    
    def update_size(self):
        '''
        sends a head request to get the size of the file update ``self.size``.
        '''
        try:
            request = requests.head(self.url, timeout=self.timeout)
            request.raise_for_status()
            if 'Content-Range' in request.headers:
                content_range = request.headers['Content-Range'].split()
                size = content_range[1].split('/')[1]
                self._set_size(int(size))
            elif 'Content-Length' in request.headers:
                self._set_size(int(request.headers['Content-Length']))
            else:
                self._set_size(-1)
        except Exception as e:
            pass
    
    def _update_speed(self):
        '''
        recalculate download speed. you should not call this method. it is
        periodically called when the downloader starts.
        '''
        t = time.monotonic()
        d = self.downloaded
        dt = t - self.last_speed_update
        dd = d - self.last_speed_downloaded
        self.last_speed_update = t
        self.last_speed_downloaded = d
        if dt != 0:
            self._speed = dd / dt
            self.emit('speed-changed', self)
    
    def bar(self, width=30, char='=', unknown='?'):
        '''
        returns a string of width ``width`` representing a progress bar.
        the string is filled with ``char`` and spaces. the number of ``char``
        represents the part of the file downloaded (e.g., if half of the file
        is downloaded, half of the string will be filled with ``char``). the rest
        of the string will be filled with spaces. if the ratio of downloaded
        data is not known, returns a string of width ``width`` filled with the
        ``unknown`` argument.
        
        args:
            * width (int): number of characters in the bar.
            * char (str) character to fill the bar with.
            * unknown (str): character to fill the bar if the ratio downloaded is
                unknown.
        
        returns:
            a string containing ``width`` characters filled with ``char`` and spaces
            to show the ratio of the downloaded bytes to the total file size.
            
            examples:
                if the width is 8 and 25% of the file is downloaded, the
                returned string will be '==      '
                
                if the width is 8 and the ratio downloaded is not known, the
                returned string will be '????????'
                
        '''
        if self.ratio >= 0:
            return (int(width * self.ratio) * char).ljust(width)
        else:
            return str(None).center(width)
    
    @property
    def url(self):
        return self._url
    
    @url.setter
    def url(self, value):
        with self._lock:
            if not self.is_alive:
                self._url = value
            else:
                raise RuntimeError('download must be stopped')
        self.emit('url-changed', self)
    
    @property
    def path(self):
        return self._path
    
    @path.setter
    def path(self, value):
        with self._lock:
            if not self.is_alive:
                if not isinstance(value, io.BufferedIOBase):
                    self._path = pathlib.Path(value)
                else:
                    self._path = value
            else:
                raise RuntimeError('download must be stopped')
        self.emit('path-changed', self)
    
    @property
    def chunk_size(self):
        return self._chunk_size
    
    @chunk_size.setter
    def chunk_size(self, value):
        with self._lock:
            if self.is_alive:
                print('new chunk_size will take effect when download is restarted', file=sys.stderr)
            
            #avoid long sleeps when chunk_size is higher than rate_limit.
            if self._bytes_per_period > 0:
                value = min(value, self._bytes_per_period)
            if value <= 0:
                raise ValueError('chunk_size must be greater than 0')
            self._chunk_size = value
    
    @property
    def timeout(self):
        return self._timeout
    
    @timeout.setter
    def timeout(self, value):
        with self._lock:
            if self.is_alive:
                print('new timeout will take effect when download is restarted', file=sys.stderr)
            
            self._timeout = value
    
    @property
    def rate_limit(self):
        return self._bytes_per_period / self.update_period
    
    @rate_limit.setter
    def rate_limit(self, value):
        self._bytes_per_period = value * self.update_period
        if self._bytes_per_period > 0 and self._bytes_per_period < self.chunk_size:
            self.chunk_size = self._bytes_per_period
        self.emit('rate-limit-changed', self)
    
    @property
    def human_rate_limit(self):
        value = human_readable(self.rate_limit)
        return value[0], value[1] + '/s'
    
    @property
    def update_period(self):
        return self._update_period
    
    @update_period.setter
    def update_period(self, value):
        old_rate_limit = self.rate_limit
        self._update_period = value
        self.rate_limit = old_rate_limit
    
    @property
    def restart_wait(self):
        return self._restart_wait
    
    @restart_wait.setter
    def restart_wait(self, value):
        self._restart_wait = value
        if self.is_restarting:
            print('currently restarting. will reset restart with new restart_wait', file=sys.stderr)
            self.restart()
    
    @property
    def restart_time(self):
        return self._restart_time
    
    def _set_restart_time(self, value):
        '''
        sets ``self.restart_time`` property. this method is for internal class use
        and you should not call it.
        
        args:
            * value (int): the new restart time.
        '''
        self._restart_time = value
        self.emit('restart-time-changed', self)
    
    @property
    def is_alive(self):
        return self._thread.is_alive()
    
    @property
    def is_restarting(self):
        return self._restart_thread.is_alive()
    
    @property
    def state(self):
        return self._state
    
    @property
    def size(self):
        return self._size
    
    @property
    def human_size(self):
        return human_readable(self.size)
    
    @property
    def ratio(self):
        if self.size == 0:
            return 1.0
        elif self.size > 0:
            return self.downloaded / self.size
        else:
            return -1.0
    
    @property
    def percentage(self):
        return 100 * self.ratio
    
    @property
    def downloaded(self):
        return self._downloaded
    
    @property
    def human_downloaded(self):
        return human_readable(self.downloaded)
    
    def _set_downloaded(self, value):
        '''
        sets ``self.downloaded`` property. this method is for internal class
        use and you should not call it.
        
        args:
            * value (int): the new number of downloaded bytes.
        '''
        self._downloaded = value
    
    @property
    def remaining(self):
        if self.size >= 0:
            return self.size - self.downloaded
        else:
            return -1
    
    @property
    def human_remaining(self):
        return human_readable(self.remaining)
    
    @property
    def speed(self):
        return self._speed
    
    @property
    def human_speed(self):
        value = human_readable(self.speed)
        return value[0], value[1] + '/s'
    
    @property
    def eta(self):
        if self.remaining <= 0:
            return datetime.timedelta(seconds=0)
        elif self.speed == 0:
            return None
        else:
            return datetime.timedelta(seconds=self.remaining/self.speed)
    
    @property
    def last_exception(self):
        return self._last_exception

class Manager(Emitter):
    '''
    download manager class. multiple urls can be added to it. you can specify
    the maximum number of downloads that run at a single time and the manager
    will start or stop downloads to reach and not exceed this number. you can
    also specify the total download rate limit and the manager class will
    equally divide the speed over the running downloads.
    
    the ``Manager`` class subclasses ``Emitter`` and emits signals when a
    download is added or removed.
    
    properties:
    
    ============  =======  ======  =============================================
    name          type     access  description
    ============  =======  ======  =============================================
    rate_limit    `int`    RW      rate limit for all running downloads. it will
                                   be divided equally over the them. a value
                                   <= 0 means no rate limit.
    max_running   `int`    RW      maximum running downloads at a single time.
                                   if the number of started downloads exceed
                                   this number, the manager will stop some
                                   downloads. if the number is less than this
                                   number, the manager will start some
                                   downloads. a value <= 0 means no limit.
    restart_wait  `float`  RW      minimum time before the manager starts the
                                   same download. even if max_running is not
                                   reached, if ``restart_wait`` has not passed
                                   since the download last stopped, the download
                                   not started immediately. the manager will
                                   wait until this number of seconds has passed
                                   then start the download. this is to prevent
                                   frequent restarts in case of network failure.
    kwargs        `dict`   RW      keyword arguments to added downloads when
                                   creating an instance of `Downloader` using
                                   `self.add()`
    downloads     `list`   R       downloads added to this manager. a list
                                   containing `Downloader` instances.
    ============  =======  ======  =============================================
    
    signals:
        * add: emitted when a new ``Downloader`` is added. the signal's callbacks
            take 2 positional arguments, the ``Manager`` instance that emitted the
            signal and the ``Downloader`` that was just added. the added
            ``Downloader`` can be found in ``self.downloads``.
        * remove: emitted when a ``Downloader`` is removed. the signal's callbacks
            take 2 positional arguments, the ``Manager`` instance that emitted the
            signal and the ``Downloader`` that was just removed. the removed
            ``Downloader`` can no longer be found in ``self.downloads``.
        * property-changed: emitted when `rate_limit`, `max_running`,
            `restart_wait` or `kwargs` property is changed.
        
    '''
    
    __signals__ = [
            'add',
            'remove',
            'property-changed',
        ]
    
    def __init__(self, max_running=0, rate_limit=0, restart_wait=30, **kwargs):
        '''
        constructor.
        args:
            * max_running (int): sets ``self.max_running`` property.
            * rate_limit (float): sets ``self.rate_limit`` property.
            * restart_wait (float): sets ``self.restart_wait`` property.
            * **kwargs: sets ``self.kwargs`` property.
        '''
        super().__init__()
        
        self._max_running = max_running
        self._rate_limit = rate_limit
        self.restart_wait = restart_wait
        self.kwargs = kwargs
        self._downloads = []
        self._q = queue.Queue()
        self._thread = threading.Thread(target=self._do_start)
        self._schedule_thread = threading.Timer(
                0,
                self.update
            )
        self._lock = threading.RLock()
    
    @property
    def rate_limit(self):
        return self._rate_limit
    
    @rate_limit.setter
    def rate_limit(self, value):
        self._rate_limit = value
        self.emit('property-changed', self, 'rate-limit')
        self.update()
    
    @property
    def human_rate_limit(self):
        return human_readable(self.rate_limit)
    
    @property
    def max_running(self):
        return self._max_running
    
    @max_running.setter
    def max_running(self, value):
        self._max_running = value
        self.emit('property-changed', self, 'max_running')
        self.update()
    
    @property
    def restart_wait(self):
        return self._restart_wait
    
    @restart_wait.setter
    def restart_wait(self, value):
        self._restart_wait = value
        self.emit('property-changed', self, 'restart_wait')
    
    @property
    def kwargs(self):
        return dict(self._kwargs)
    
    @kwargs.setter
    def kwargs(self, value):
        self._kwargs = dict(value)
        self.emit('property-changed', self, 'kwargs')
    
    @property
    def downloads(self):
        return [x[0] for x in self._downloads]
    
    def start(self):
        '''
        start download manager thread. after a call to this method, the manager
        will start checking added downloads to start, stop and change rate limit
        when necessary.
        '''
        with self._lock:
            if not self._thread.is_alive():
                self._thread = threading.Thread(target=self._do_start)
                self._thread.start()
    
    def _do_start(self):
        '''
        called by ``self.start()``. you should not call this method since it is
        for internal class use.
        '''
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        
        self.update()
        while True:
            msg = self._q.get()
            self._schedule_thread.cancel()
            if msg:
                break
            
            self._do_update()
    
    def stop(self):
        '''
        stop the manager thread.
        '''
        self._q.put(True)
    
    def add(self, d):
        '''
        add a new download to the manager.
        
        args:
            * d (str or ``Downloader``): the url or ``Downloader`` instance to
                add. if ``d`` type is str, a new ``Downloader`` instance is
                created with arguments taken from `self.kwargs` property.
        returns:
            the ``Downloader`` instance added.
        '''
        with self._lock:
            if not isinstance(d, Downloader):
                d = Downloader(d, **self.kwargs)
            if d not in self.downloads:
                self._downloads.append([d, False, -1])
                d.listen('state-changed', self._on_state_changed)
                self.update()
                self.emit('add', self, d)
                return d
    
    def stop_all(self):
        '''
        pause all currently running downloads. the manager thread is not
        stopped. if you want to stop the manager and all downloads, call
        ``self.stop()`` first.
        '''
        with self._lock:
            t = time.monotonic()
            for c in self._downloads:
                if c[1]:
                    c[0].stop()
                    c[2] = t
    
    def update(self):
        '''
        tell the manager thread to check pending downloads to see if there is
        need to start, stop or change rate limit to some of them. this is called
        automatically when the state of any added download changes and when
        manager properties are changed. you do not need to call it.
        '''
        if self._thread.is_alive():
            self._q.put(False)
    
    def _schedule_update(self, t):
        '''
        schedule an update. you should not call this method since it is for
        internal class use.
        
        args:
            t (float): time to wait before updating.
        '''
        self._schedule_thread = threading.Timer(
                t,
                self.update,
            )
        self._schedule_thread.start()
    
    def _do_update(self):
        '''
        actual checks on the added downloads happen in this method. you should
        not call this method since it is for internal class use. call
        ``self.update()``
        '''
        with self._lock:
            t = time.monotonic()
            
            #flag fatal and completed downloads as paused
            not_checked = [
                    df for df in self._downloads if (
                            df[1] and df[0].state in ['complete', 'fatal-error']
                        )
            ]
            for df in not_checked:
                df[1] = False
                df[2] = t
            
            #seperate downloads flagged as started or paused
            #sort them by last state change time
            started = [df for df in self._downloads if df[1]]
            started.sort(key=lambda df: df[2])
            paused = [
                    df for df in self._downloads if (
                            not df[1] and
                            df[0].state not in ['fatal-error', 'complete']
                        )
                ]
            paused.sort(key = lambda df: df[2])
            
            #get downloads flagged as started which were stopped out of manager
            #mark them as paused and move them to paused list
            pstarted = [
                    df for df in started if (
                            df[0].state in ['error', 'pause']
                        )
                ]
            for df in pstarted:
                df[1] = False
                df[2] = t
                idx = started.index(df)
                started.pop(idx)
                paused.append(df)
            
            #get downloads flagged as paused which were started out of manager
            #mark them as started and move them to started list
            spaused = [
                    df for df in paused if (
                            df[0].state in ['start', 'download']
                        )
                ]
            for df in spaused:
                df[1] = True
                df[2] = t
                idx = paused.index(df)
                paused.pop(idx)
                started.append(df)
            
            #pause downloads if we exceed self.max_running
            if self.max_running > 0:
                while len(started) > self.max_running:
                    df = started.pop(0)
                    df[0].stop()
                    df[1] = False
                    df[2] = t
                    paused.append(df)
            
            #filter downloads that were not paused only recently
            to_start = [df for df in paused if df[2] <= t - self.restart_wait]
            
            #start downloads if we are still below self.max_running
            while (
                    (
                            self.max_running <= 0 or
                            len(started) < self.max_running
                        ) and
                    to_start
                ):
                df = to_start.pop(0)
                started.append(df)
            
            #if there are downloads marked as started
            #then set rate limit for each download and start those flagged but
            #not actually started
            if len(started):
                if self.rate_limit > 0:
                    rate = max(1, self.rate_limit // len(started))
                else:
                    rate = self.rate_limit
                for df in started:
                    df[0].rate_limit = rate
                    if not df[1]:
                        df[1] = True
                        df[2] = t
                        df[0].start()
            
            t = [df[2] for df in paused if df[2] > t - self.restart_wait]
            if t:
                t = min(t) + self.restart_wait - time.monotonic()
                self._schedule_update(t)
    
    def remove(self, d):
        '''
        remove a previously added download then emits ``remove`` signal. if the
        download is running, it is not stopped.
        
        args:
            * d (``Downloader``): the downloader to remove.
        '''
        self._remove(d)
        self.emit('remove', self, d)
    
    def _remove(self, d):
        '''
        remove a previously added download. if the download is running, it is
        not stopped. this function is for internal class use and you should not
        call it.
        
        args:
            * d (``Downloader``): the downloader to remove.
        '''
        with self._lock:
            idx = self.downloads.index(d)
            dl = self._downloads.pop(idx)[0]
            dl.unlisten('state-changed', self._on_state_changed)
            self.update()
    
    def _on_state_changed(self, d=None, old_state=None):
        '''
        callback to be called when ``state-changed`` signal is emitted from any
        of the managed downloads.
        '''
        self.update()

def main(urls, rate_limit='0', max_running=5):
    '''
    downloads the given urls until done downloading them all. displays
    statistics about downloads in the following format:
    s | speed | downloaded | percent | eta | name
        
    in the above format, the first item `s` is the first letter of the state of
    the download. for example, for complete downloads, that would be the
    letter `c`. Similarly, `e` would be for error and `f` for fatal error.
    `speed` is the download speed in human readable format. `downloaded` is the
    number of downloaded bytes in human readable format. `percent` is percentage
    downloaded. `eta` is estimated time to complete the download. `name` is the
    name of the file being downloaded or part of the name if the name is very
    long.
    
    args:
        * urls: the urls to download.
        * rate_limit: total rate limit for all downloads
        * max_running: maximum running downloads at any given time
    '''
    
    if type(urls) is str:
        urls = [urls]
    
    urls = set(urls)
    
    if not rate_limit.isdigit():
        multiplier = {'k': 2**10, 'm': 2**20}[rate_limit[-1].lower()]
        rate_limit = float(rate_limit[:-1]) * multiplier
    
    rate_limit = int(rate_limit)
    
    def update():
        LINES = min(24, len(m.downloads))
        while True:
            downloads = [c for c in m.downloads if c.is_alive and
                c.state != 'complete'][:LINES]
            downloads += [c for c in m.downloads if not c.is_alive and
                c.state != 'complete'][:LINES-len(downloads)]
            downloads += [c for c in m.downloads if not c.is_alive and
                c.state == 'complete'][:LINES-len(downloads)]
            
            print('\033[H', end='')
            for idx, d in enumerate(downloads):
                eta = d.eta
                if eta is not None:
                    eta = datetime.timedelta(seconds=int(eta.total_seconds()))
                
                info = []
                info.append(d.state[0])
                info.append('{0[0]:>7.2f} {0[1]:>4}'.format(d.human_speed))
                info.append('{0[0]:>7.2f} {0[1]:>2}'.format(d.human_downloaded))
                info.append('{0:>7.2f}%'.format(d.percentage))
                info.append('{:>8}'.format(str(eta)))
                info.append(d.path.name[-25:])
                info = ' | '.join(info).ljust(79)
                
                print('{}'.format(info))
            
            for c in range(LINES-len(downloads)):
                print('{}'.format(''.ljust(79)))
            
            print('running {:>3} | completed {:>3} / {:>3}'.format(
                len([c for c in m.downloads if c.is_alive]),
                len([c for c in m.downloads if c.state == 'complete']),
                len(m.downloads)))
            
            if [c for c in m.downloads if c.state != 'complete']:
                time.sleep(2)
            else:
                break
    
    m = Manager(rate_limit=rate_limit, max_running=max_running)
    
    for c in urls:
        m.add(c)
    m.start()
    
    try:
        update()
    finally:
        m.stop()
        m.stop_all()

if __name__ == '__main__':
    import argparse
    
    desc = '''
    downloads the given urls until done downloading them all. displays
    statistics about downloads in the following format:
        s | speed | downloaded | percent | eta | name
        
    in the above format, the first item `s` is the first letter of the state of
    the download. for example, for complete downloads, that would be the
    letter `c`. Similarly, `e` would be for error and `f` for fatal error.
    `speed` is the download speed in human readable format. `downloaded` is the
    number of downloaded bytes in human readable format. `percent` is percentage
    downloaded. `eta` is estimated time to complete the download. `name` is the
    name of the file being downloaded or part of the name if the name is very
    long.
    
    args:
        * urls: the urls to download.
        * rate_limit: total rate limit for all downloads
        * max_running: maximum running downloads at any given time
    '''
    
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('urls', nargs='+', help='urls to download.')
    parser.add_argument('-r', '--rate-limit', type=str, default='0',
        help='rate limit. can be specified as megabytes or kilobytes (e.g. 0.5m for 0.5 megabytes per second, 100k for 100 kilobytes per second). a value <= 0 means no limit.')
    parser.add_argument('-m', '--max-running', type=int, default=5,
        help='maximum number of downloads to be running at one time. a value <= 0 means no limit.')
    
    namespace = parser.parse_args()
    main(**vars(namespace))

