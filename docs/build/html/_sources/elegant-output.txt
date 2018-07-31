==============
Elegant Output
==============

We are finally in the last lesson. Let's make our output beautiful.

Our goal will be to make the output look like this::

    <state> | <File size> | <Downloaded> | <speed> [<progress bar>] <percentage>% <eta>

We have all the information in 1 line seperated by a pipe character "|". The
state will show us in real time if there is any error. The file size, downloaded
bytes and speed will be in human readable form so that we can easily read it.
The progress bar will indicate how much portion we have downloaded so far. The
percentage will indicate the same as the progress bar but in numbers. Finally,
``eta`` is the estimated time to finish the download. The information will be
printed in only 1 line. If it changes, we will make the information be updated
in the same line instead of printing so many lines like we did in the
``on_speed_changed`` callback.

-------------------------------
Showing information in one line
-------------------------------

First, instead of having a callback function for each signal, let's make 1
callback that will update all the information whenever 1 thing changes. Let's
remove ``on_size_changed``, ``on_speed_changed`` and ``on_state_changed``
callbacks and write 1 callback to print the ``state``, ``size``, ``downloaded``,
and ``speed`` instead::

    def on_anything_changed(downloader, old_state=None):
        state = downloader.state
        size = '{} {}'.format(*downloader.human_size)
        downloaded = '{} {}'.format(*downloader.human_downloaded)
        speed = '{} {}'.format(*downloader.human_speed)
        
        text = '{} | {} | {} | {}'.format(state, size, downloaded, speed)
        print(text)

We will do the progress bar, the percentage and the estimated download time in a
later section.

Next, we modify all ``Downloader.listen()`` calls to register the new function::

    #listen to everything
    dl.listen('size-changed', on_anything_changed)
    dl.listen('speed-changed', on_anything_changed)
    dl.listen('state-changed', on_anything_changed)

Now our callback will be called when the state changes, when we know the
size and periodically when ``speed-change`` signal is emitted. Notice that we
also printed number of bytes ``downloaded`` which we did not do in previous
lessons. Now our output will be something like this::

    pause | 9.865234375 KB | 0 B | 0 B/s
    start | 9.865234375 KB | 0 B | 0 B/s
    start | 9.865234375 KB | 0 B | 0 B/s
    start | 9.865234375 KB | 2.0 KB | 1.9990254031527928 KB/s
    start | 9.865234375 KB | 4.0 KB | 1.9989961600987338 KB/s
    start | 9.865234375 KB | 6.0 KB | 1.9988544205541783 KB/s
    start | 9.865234375 KB | 8.0 KB | 1.9987502773920875 KB/s
    start | 9.865234375 KB | 9.865234375 KB | 1.9987502773920875 KB/s
    complete | 9.865234375 KB | 9.865234375 KB | 0 B/s
    complete | 9.865234375 KB | 9.865234375 KB | 0 B/s

Ok. We still have ugly output. First, let's make all numbers rounded to 2
decimal places. In the callback, we will modify our ``format strings``::

    state = downloader.state
    size = '{:0.2f} {}'.format(*downloader.human_size)
    downloaded = '{:0.2f} {}'.format(*downloader.human_downloaded)
    speed = '{:0.2f} {}'.format(*downloader.human_speed)

Second, we do not want to print multiple lines. We want to print only 1 line.
Let's use the ``print`` function arguments to stay on the same line and use the
character ``\r`` to update it::

    text = '\r{} | {} | {} | {}'.format(state, size, downloaded, speed)
    print(text, end='', flush=True)

Now our callback will not print many lines. Instead, it will go back to the
beginning of the line and print the information on the same line erasing
anything previously shown.

Furthermore, let's modify the ``print`` call to print spaces to fill all the
line with 79 characters just to erase the whole line in case we have garbage out
of our text width::

    print(text.ljust(79), end='', flush=True)

Our callback now becomes::

    def on_anything_changed(downloader, old_state=None):
        state = downloader.state
        size = '{:0.2f} {}'.format(*downloader.human_size)
        downloaded = '{:0.2f} {}'.format(*downloader.human_downloaded)
        speed = '{:0.2f} {}'.format(*downloader.human_speed)
        
        text = '\r{} | {} | {} | {}'.format(state, size, downloaded, speed)
        print(text.ljust(79), end='', flush=True)

--------------------------------------------
Showing the progress bar, percentage and ETA
--------------------------------------------

Let's start with the progress bar. We use ``Downlaoder.bar()`` function to
generate a progress bar. The function takes 2 optional arguments. The first is
``width`` which is the length in characters of the progress bar. It defaults to
30. Let's make it 10. The second is ``char`` which is the character to
use to fill the bar. It defaults to '='. Let's make this a dash instead::

    bar = downloader.bar(width=10, char='-')

Our callback now becomes::

    def on_anything_changed(downloader, old_state=None):
        state = downloader.state
        size = '{:0.2f} {}'.format(*downloader.human_size)
        downloaded = '{:0.2f} {}'.format(*downloader.human_downloaded)
        speed = '{:0.2f} {}'.format(*downloader.human_speed)
        bar = downloader.bar(width=10, char='-')
        
        text = '\r{} | {} | {} | {} [{}]'.format(
                state,
                size,
                downloaded,
                speed,
                bar
            )
        print(text.ljust(79), end='', flush=True)

Notice how we enclosed the progress bar in brackes within our format string.

Percentage and ETA are straight forward. We use ``Downloader.percentage`` and
``Downloader.eta`` properties of the downloader::

    percentage = int(downloader.percentage)
    eta = downloader.eta

``Downloader.percentage`` property returns the percentage (from 0 to 100) as a
``float``. we converted it to ``int`` to remove any digits after the decimal
point to reduce user confusion. eta returns a ``datetime.timedelta`` instance
which tells us the estimated time remaining until the download is completed.

Now our full callback function becomes::

    def on_anything_changed(downloader, old_state=None):
        state = downloader.state
        size = '{:0.2f} {}'.format(*downloader.human_size)
        downloaded = '{:0.2f} {}'.format(*downloader.human_downloaded)
        speed = '{:0.2f} {}'.format(*downloader.human_speed)
        bar = downloader.bar(width=10, char='-')
        percentage = int(downloader.percentage)
        eta = downloader.eta
        
        text = '\r{} | {} | {} | {} [{}] {}% {}'.format(
                state,
                size,
                downloaded,
                speed,
                bar,
                percentage,
                eta
            )
        print(text.ljust(79), end='', flush=True)

And now, this is our awesome program::

    import bitpit
    import pathlib
    
    def on_anything_changed(downloader, old_state=None):
        state = downloader.state
        size = '{:0.2f} {}'.format(*downloader.human_size)
        downloaded = '{:0.2f} {}'.format(*downloader.human_downloaded)
        speed = '{:0.2f} {}'.format(*downloader.human_speed)
        bar = downloader.bar(width=10, char='-')
        percentage = int(downloader.percentage)
        eta = downloader.eta
        
        text = '\r{} | {} | {} | {} [{}] {}% {}'.format(
                state,
                size,
                downloaded,
                speed,
                bar,
                percentage,
                eta
            )
        print(text.ljust(79), end='', flush=True)
    
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
    
    #listen to everything
    dl.listen('size-changed', on_anything_changed)
    dl.listen('speed-changed', on_anything_changed)
    dl.listen('state-changed', on_anything_changed)
    
    #start downloading and tell user download has started.
    dl.start()
    print('Download has started.')
    
    #end of the main thread

The output I got from this program is below::

    start | 9.87 KB | 4.00 KB | 2.00 KB/s [----      ] 40% 0:00:02.934069

You can see that fractions of a second are shown in ``eta`` which is not very
nice. However, I will leave this to you to fix.

Finally we have an awesome download program. Of course, there are many things
we can improve on it. But I believe this form is enough to explain bitpit
features and how to use it.

You may want to have a look at :doc:`reference` for complete documentation of
the library.

THE END...

