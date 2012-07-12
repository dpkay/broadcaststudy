import gdata.youtube
import gdata.youtube.service

yt_service = gdata.youtube.service.YouTubeService()
yt_service.email = 'christinechenvideos'
yt_service.password = 'XXXXXXX INSERT PASSWORD HERE XXXXXXX'
yt_service.source = 'myApp'
yt_service.ProgrammaticLogin()


entries = []
startIndex = 0
while True:
  if startIndex > 0:
    uri = "https://gdata.youtube.com/feeds/api/users/default/uploads" \
          "?max-results=50&start-index=%d" % startIndex
  else:
    uri = "https://gdata.youtube.com/feeds/api/users/default/uploads" \
          "?max-results=50"
  #print uri
  feed = yt_service.GetYouTubeVideoFeed(uri)
  for entry in feed.entry:
    #entries += (entry.media.title.text, entry.GetSwfUrl())
    print "- title: " + entry.media.title.text
    print "  url: " + entry.GetSwfUrl()
    print

  if len(feed.entry) < 50:
    break
  startIndex += 50

  #if startIndex > 50:
  #  break

#print entries
#print len(entries)
