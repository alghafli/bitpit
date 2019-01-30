=================
Additional Tuning
=================

Now we have most of our work done. We are going to look into a few minor
additional things we can do to modify our downloader behaviour.

------------------
Connection Timeout
------------------

We can change the connection timeout settings by giving the ``timeout`` argument
to ``Downloader.__init__()``. The default value is 10 seconds. That is relatively
small. Let's make it 1 minute::

    dl = bitpit.Downloader(
            url,
            path=pathlib.Path.home() / 'Desktop' / 'logo.png',
            restart_wait=30,
            rate_limit=2048,
            timeout=60
        )

----------
Chunk Size
----------

We can also supply the download ``chunk_size`` to ``Downloader.__init__()``.
The chunk size is the maximum number of bytes to download in a single network
read operation. You do not really need to change this at all but just in case
you want to change it. Having very low or very high values may slightly affect
download speed. There is no hard rule to figure out the best other than trying.
In my computer, the default value worked best. The default value is 4 KB. For
practice, let's change it to 1 KB::

    dl = bitpit.Downloader(
            url,
            path=pathlib.Path.home() / 'Desktop' / 'logo.png',
            restart_wait=30,
            rate_limit=2048,
            timeout=60,
            chunk_size=1024
        )

The ``chunk_size`` cannot be greater than ``rate_limit``. If it is greater,
`bitpit` will force it to be equal to ``rate_limit``.

Here is our program so far::

    import bitpit
    import pathlib
    
    def on_size_changed(downloader):
        print('The file size is', downloader.size)
    
    def on_speed_changed(downloader):
        print('The speed is', *downloader.human_speed)
    
    def on_state_changed(downloader, old_state):
        print('The state changed to:', downloader.state)
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(
            url,
            path=pathlib.Path.home() / 'Desktop' / 'logo.png',
            restart_wait=30,
            rate_limit=2048,
            timeout=60,
            chunk_size=1024
        )
    
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

Now we have only one thing left to do. If you have noticed, our output is ugly.

In :doc:`elegant-output` we are going to make it pretty. We will also introduce some
useful things in `bitpit`.

