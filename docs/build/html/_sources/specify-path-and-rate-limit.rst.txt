============================
Specify Path and Rate Limit
============================

So far our program gives us most of the information we need and also restarts
when an error occures. There are 2 things we will do in this lesson: First we
will specify where we want to save our file and second we want to limit the
download speed so that the internet does not become slow for the rest of the
family. I grouped the two in 1 lesson because both are straight forward.

---------------------
Specify the file path
---------------------

We want to decide where our file will be saved. This is done using the ``path``
argument to ``Downloader.__init__()``::

    dl = Downloader(url, path='~/Desktop/logo.png', restart_wait=30)

The above instruction tells the downloader to save the file in my desktop with
the name ``logo.png``. In case you do not know what ``~`` means in a path, it
means the user home directory in linux systems. This will probably not work on
windows. We can make a portable way that works in both linux and windows by
importing and using ``pathlib`` standard python library::
    
    dl = Downloader(
            url,
            path=pathlib.Path.home() / 'Desktop' / 'logo.png',
            restart_wait=30
        )

If you are not familiar with ``pathlib``, then you should have a look at this
awsome library.

You notice that in our first modification above, we supplied a python string in
the ``path`` argument. However, in our second modification, we gave a
``pathlib.Path`` object. The argument ``path`` can take both. In fact, you can
give anything that ``pathlib.Path.__ini__()`` supports. If you want, you can also
give a binary file-like object and the data will be saved in it.

-------------------
Download rate limit
-------------------

To limit the download rate, you simply give ``rate_limit`` argument to
``Downloader.__init__()``::

    dl = Downloader(
            url,
            path=pathlib.Path.home() / 'Desktop' / 'logo.png',
            restart_wait=30,
            rate_limit=2048
        )

In our example here, we made our maximum download speed 2 KB/s. Let's see the
program output now::

    The file size is 10102
    The speed is 0 B/s
    The state changed to: start
    The speed is 1.9989241550312336 KB/s
    The speed is 1.9988802572634587 KB/s
    The speed is 1.9987825036005515 KB/s
    The speed is 1.9989528185814844 KB/s
    The file size is 10102
    The speed is 0 B/s
    The state changed to: complete

You can see that the download speed became very close to 2 KB/s (or a little
less). However, note that this may not work as expected for small files.

Our full program so far became::

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
            rate_limit=2048
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

In :doc:`additional-tuning`, we will do our final tunes to our downloader.

