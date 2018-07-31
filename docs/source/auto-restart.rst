=================
Automatic Restart
=================

So far, our program freezes until the download stops. However, when the program
ends we are not sure whether the file is stopped because it is completely
downloaded or because an error occured. What if an error occured and we want to
restart the download again? This is easy. We just pass ``restart_wait`` argument
to ``Downloader.__init__()``::

    dl = bitpit.Downloader(url, restart_wait=30)

This argument decides the time to wait before the downloader retries downloading
when an error occures. It defaults to -1 if not given which means do not restart
even after an error. Because we gave it the value 30 here, anytime an error
happens, the downloader will wait for 30 seconds and then retry again. Try to
download `linux mint <http://mirrors.evowise.com/linuxmint/stable/18.3/
linuxmint-18.3-cinnamon-64bit.iso>`_ and shutdown your internet connection. Here
is the output I got::

    The file size is 1899528192
    The speed is 0 B/s
    The state changed to: start
    The speed is 207.0622560278128 KB/s
    The speed is 474.6406851817469 KB/s
    The speed is 0 B/s
    The state changed to: error
    The file size is 1899528192
    The speed is 0 B/s
    The state changed to: start
    The speed is 506.2438224533826 KB/s
    The speed is 594.6743846283302 KB/s

You can see the state has changed to ``error`` after I shutdown my internet but
the program did not terminate. After 30 seconds, the state changed again to
``start`` and the download continued. Now our program will only terminate when
the download is successfully completed.

One last note, some connection errors are perminant. For instance, if you get a
404 NOT FOUND error, then no matter how many times you try, the error will keep
happening. bitpit does not handle that and will keep trying to download
regardless of the error. You can check the error that happened by looking at the
``Downloader.last_exception`` property. You will most probably get an exception
from ``requests.exceptions`` module.

We have only changed 1 line in this lesson. Now our program so far has become::

    import bitpit
    
    def on_size_changed(downloader):
        print('The file size is', downloader.size)
    
    def on_speed_changed(downloader):
        print('The speed is', *downloader.human_speed)
    
    def on_state_changed(downloader, old_state):
        print('The state changed to:', downloader.state)
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(url, restart_wait=30)
    
    #listen to signals
    #print size as soon as it is known
    dl.listen('size-changed', on_size_changed)
    
    #print speed periodically
    dl.listen('speed-changed', on_speed_changed)
    
    #print state
    dl.listen('state-changed', on_state_changed)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

We are getting closer to the end.

In :doc:`specify-path-and-rate-limit`, we will specify the path and name to
save our file instead of saving it in the current directory with the default
name. We will also start limiting the download speed instead of eating up all
our internet bandwidth before my brother gets angry.

