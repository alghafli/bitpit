import bitpit

url = 'https://www.python.org/static/img/python-logo.png'    #will download this
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
#the following call will not block
d.start()

#do some other work...

#wait for download completion or error if you want
d.join()

