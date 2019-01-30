===========
Quick Guide
===========

This is a quick guide to use the library. Read it if you want to have a quick
look in the library and do not want to spend much time here.

bitpit is an event driven http download library with automatic resume and other
features. The library is written in an event-driven style similar to GTK+.

---------------
Usage example
---------------

This is a typical usage example::
    
    import bitpit
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    d = bitpit.Downloader(url) #downloader instance
    
    #listen to download events and call a function whenever an event happens
    #print state when state changes
    d.listen(
            'state-changed',
            lambda var, old_state: print('download state:', var.state)
        )
    
    #print speed in human readable format whenever speed changes
    #speed is updated and callback is called every 1 second by default
    d.listen(
            'speed-changed',
            lambda var: print('download speed:', *var.human_speed)
        )
    
    #register another callback function to the speed change signal
    #print percentage downloaded whenever speed changes
    d.listen('speed-changed', lambda var: print(int(var.percentage), '%'))
    
    #print total file size in human readable format when the downloader knows the file size
    d.listen(
            'size-changed',
            lambda var: print('total file size:', *var.human_size)
        )
    
    #done registering callbacks. lets start our download
    #the following call will not block. it will start a new download thread
    d.start()
    
    #do some other work while download is taking place...
    
    #wait for download completion or error
    d.join()


--------------
As main script
--------------

This module can also be run as a main python script to download a file. You can have a look at the main function for another usage example.

commandline syntax::

    python -m bitpit.py <url>
    
args:

    * url: the url to download.

---------------
Other arguments
---------------

Most of what you can do is done by passing the desired args to
``Downloader.__init__()``. Here are most of the args you can use:

#. url: URL to download
#. path: The path to download the file at. if not supplied, will guess the file
         name from the URL.
#. restart_wait: Time to wait in case of error before the download is retried.
                 If not supplied, will never retry in case of error.
#. update_period: The minimum time to wait before emitting *speed-changed*
                  signal. Defaults to 1 second.
#. timeout: Connection timeout. Defaults to 10 seconds.
#. rate_limit: Maximum download bit rate. If not supplied, download without
               speed limit.

--------
Tutorial
--------
In :doc:`download-a-file` you will find a more comprehensive bitpit tutorial.

