:Date: 2019-01-30
:Version: 1.1.1
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

    python -m bitpit.py <url>
    
args:
    * url: the url to download.

--------
Tutorial
--------

Check out bitpit tutorial at http://bitpit.readthedocs.io/

