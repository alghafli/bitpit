===============
Download a File
===============

So we have bitpit installed and ready. Let's start using it. In this tutorial we
are going to make a little download program. It is a little bit similar to the
downloader function but we will make it a little bit better.

First, we need to import the library::

    import bitpit

Now let's specify the URL we are going to download. We are going to download
python logo::

    url = 'https://www.python.org/static/img/python-logo.png'

Next comes bitpit business. We create a ``Downloader`` instance::

    dl = bitpit.Downloader(url)

Finally we start the download::

    dl.start()
    print('Download has started.')

Now the download will start. Notice that ``Downloader.start()`` call will not
block. The message ``Download has started.`` will be printed immediately before
the download finishes. Then our main thread will end but the downloading thread
will keep running until the file is fully downloaded or an error occures.

If you try the example above, you will see ``Download has started`` message
printed on the screen and nothing else. The program will freeze until the
download finishes. Imagine if we have a very big file such as `linux mint
<http://mirrors.evowise.com/linuxmint/stable/18.3/
linuxmint-18.3-cinnamon-64bit.iso>`_. It will take a long time without us 
knowing how much we have downloaded. That is not so convenient isn't it? We will
look at that later but for now, let's look at the program we have written so far
::

    import bitpit
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(url)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

In :doc:`display-info`, we will make the program give us information about the download such as
whether it has started or faced an error and also the download speed.

