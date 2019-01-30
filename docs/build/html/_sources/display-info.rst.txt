============================
Display Download Information
============================

At the moment we are able to download a file. But we have no information on how
fast our download is and if it is completed or there is some error.

Before we start, here is the tiny program we made previously if you need to
refresh your mind::

    import bitpit
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(url)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

Now it is time to make it better.

---------------------
Display the file size
---------------------

If we are downloading a file, we probably want to know the file size.
bitpit is written in an event driven style. It is a little similar to GTK
library if you have used it before.
We need to do 2 steps to show the file size. First, we need to define a function
that will be called when the file size is known::

    def on_size_changed(downloader):
        print(downloader.size)

This function takes 1 argument: ``downloader`` which is the ``Downloader``
instance that we just knew its file size. In the function, we print the
``Downloader.size`` property, which is just the file size in bytes.

Next, we need to tell the downloader to call this function as soon as it knows
the file size. You probably want to do this just before you start the download.
This is done using ``Downloader.listen()`` method::

    dl.listen('size-changed', on_size_changed)

The ``Downloader.listen()`` takes at least 2 arguments. The first is the signal to
listen to. Here we listened to the ``size-changed`` signal which is emitted
whenever the downloader gets to know the size of the file being downloaded. The
second argument is the function to call when the signal is emitted. Here we put
the function we defined above.

After this call to ``Downloader.listen()``, our function will be called as soon
as the file size is known. Our full program now becomes as follows::

    import bitpit
    
    def on_size_changed(downloader):
        print('The file size is', downloader.size)
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(url)
    
    #listen to signals
    #print size as soon as it is known
    dl.listen('size-changed', on_size_changed)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

If you notice, the size is expressed in bytes. Showing the size in bytes gives
us a very big number that is difficult for humans to read. It would be easier
for us if we could display the size in Kilobytes or Megabytes. This can be done
by modifying the callback function ``on_size_changed()`` to be as follows::

    def on_size_changed(downloader):
        print('The file size is', *downloader.human_size)

We just replaced ``Downloader.size`` property with ``Downloader.human_size``
property. ``Downloader.human_size`` property gives us a 2-element tuple. The
first element is a float representing the size and the second element is a
string suffix with the value KB for kilobytes or MB for megabytes and so on.
In our call to ``print()`` function, we unpacked the tuple arguments using
python * operator. If you are not familiar with this, check it out in the python
`here <https://docs.python.org/3/tutorial/
controlflow.html#unpacking-argument-lists>`_.

When I tried the new callback function, I got the following message printed::

    The file size is 9.865234375 KB

We can use python string formatting to make it look better but we will leave it
for later.

--------------------------
Display the download speed
--------------------------

Other than the size, we want to know the download speed. Similar to the size, we
define a callback function and listen to a signal. The function we will define
will print the speed just like the size. The property we will use is
``Downloader.speed``. Also like the size, there is a ``Downloader.human_speed``.
We will use ``Downloader.human_speed``::

    def on_speed_changed(downloader):
        print('The speed is', *downloader.human_speed)

The signal we want to listen to this time is ``speed-changed``::

    dl.listen('speed-changed', on_speed_changed)

The behaviour of ``speed-changed`` signal is a little bit different than
``size-changed``. When the download starts, the signal is emitted every 1 second
. It will keep being emitted periodically as long as the download is running. In
our program, the signal will not work very well because the file size is very
small. Try to download `linux mint <http://mirrors.evowise.com/linuxmint/stable/
18.3/linuxmint-18.3-cinnamon-64bit.iso>`_ and you will see the signal working
properly.

There are other things we can do to improve our program regarding
``speed-changed`` signal. For example, we can show how much we have downloaded
so far in the callback function because we probably have downloaded something
since the last time the signal was emitted. We can check
``Downloader.downloaded`` and ``Downloader.human_downloaded`` to know that.
Furthermore, our callback will be printing a message every second which makes
the terminal full of confusing text. We can make our output better. However, we
will leave it to the end of the tutorial. For now we will stick to what we have
done so far.

Now our program has become as follows::

    import bitpit
    
    def on_size_changed(downloader):
        print('The file size is', downloader.size)
    
    def on_speed_changed(downloader):
        print('The speed is', *downloader.human_speed)
    
    #will download this
    url = 'https://www.python.org/static/img/python-logo.png'
    
    #this is our downloader
    dl = bitpit.Downloader(url)
    
    #listen to signals
    #print size as soon as it is known
    dl.listen('size-changed', on_size_changed)
    
    #print speed periodically
    dl.listen('speed-changed', on_speed_changed)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

Just as a final note in this section, you can change the time between
``speed-changed`` signal emissions in ``Downloader.__init__()`` when you create
the downloader instance by passing the desired number of seconds in the
``update_period`` argument. Check the class documentation for more details.

--------------------------
Display the download state
--------------------------

Another useful information we need in our download is its state. For example,
did it start or not? Is it completed or still in progress? Did it stop normally
or because of an error? This is what we are going to do.

Similar to the size and speed, we define a callback function and listen to a
signal::

    def on_state_changed(downloader, old_state):
        print('The state changed to:', downloader.state)


    dl.listen('state-changed', on_state_changed)

Notice that ``state-changed`` signal takes at least 2 positional argumetns.
The ``Downloader`` that changed state and the old state the downloader was on.
The ``state-changed`` signal is emitted whenever the download is started,
stopped, or completed. To know the new state, check the ``Downloader.state``
property. It can be one of the following:
* ``pause``: The download is not started or started then stopped by a calling
``Downloader.stop()`` method.
* ``start``: The download just started but is not download anything yet.
* ``download``: The download is running and in progress.
* ``error``: The download stopped bacause of an error.
* ``complete``: The download completed.

Our program now has become like this::

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
    dl = bitpit.Downloader(url)
    
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

In :doc:`auto-restart`, we will make our downloader automatically resume the download when the
download is interrupted due to an error.

