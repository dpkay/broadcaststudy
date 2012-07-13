import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import yaml
import json
import sys

from google.appengine.ext import db
from google.appengine.api import users

from protorpc import messages
from protorpc.wsgi import service
from protorpc import remote

jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


class SegmentDict(dict):
  def __init__(self, filename):
    with file(filename, 'r') as stream:
      super(SegmentDict, self).__init__(yaml.load(stream))
#      for key, clips in yaml.load(stream).iteritems()
#        self[key] = item

#distinguishedSegments = SegmentDict('distinguished_segments.yaml')

class TaskDict(dict):
  def __init__(self):
    with file('tasks.yaml', 'r') as stream:
      for item in yaml.load(stream):
        self[item['name']] = item


print "foo"
print TaskDict()

class Vote(db.Model):
  voteKey = db.StringProperty()
  value = db.IntegerProperty()
  #date = db.DateTimeProperty(auto_now_add=True)


def userId():
  user = users.get_current_user()
  if user:
    return user.user_id()
  else:
    return 0


def userKey(user_id=userId()):
  return db.Key.from_path('User', user_id)

def userName():
  return users.get_current_user().nickname()



class MainPage(webapp2.RequestHandler):
    def get(self):
        if users.get_current_user():
          logout_url = users.create_logout_url(self.request.uri)
        else:
          self.redirect(users.create_login_url(self.request.uri))
          return

        # initialize segments
        distinguishedSegments = SegmentDict('distinguished_segments.yaml')

        taskdict = {}
        for key, data in distinguishedSegments.iteritems():
          prettyName = 'D' + str(key)
          name = 'segment%03d' % key
          task = {}
          task['name'] = name
          task['prettyName'] = prettyName
          task['youtube_id1'] = data[1]
          task['youtube_id2'] = data[7]
          task['youtube_id3'] = data[8]
          taskdict[name] = task

        # initialize task
        #taskdict = TaskDict()

        # read votes from db and augment task dictionary
        votesQuery = Vote.all().ancestor(userKey())
        votes = votesQuery.fetch(500)
        for vote in votes:
          taskName, suffix = vote.voteKey.split('_') 
          taskdict[taskName]['selected_%s' % suffix] = vote.value

        # we can now throw away the keys, so
        # convert augmented task dictionary to list.
        tasks = taskdict.values()

        template_values = {
            'username': userName(),
            'logout_url': logout_url,
            'tasks': tasks
        }

        template = jinja_environment.get_template('voting_template.html')
        self.response.out.write(template.render(template_values))


class RPCHandler(webapp2.RequestHandler):
  def post(self):
    req = json.loads(self.request.body)
    action = req['action']
    if action == "vote":
      value = int(req['value'])
      result = {'status': 'undefined'}

      # test whether opposite has same value. if yes then fail
      key = req['key']
      keySplit = req['key'].split('_')
      keyOpposite = keySplit[0] + '_' + ('best' if keySplit[1] == 'worst' else 'worst')
      voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", keyOpposite)
      votes = voteQuery.fetch(1)
      if value>0 and len(votes)>0 and int(votes[0].value) == int(req['value']):
        # don't allow best and worst to have the same value
        result['status'] = "failed"

        # jump back to old value
        voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", key)
        votes = voteQuery.fetch(1)
        try:
          oldValue = votes[0].value
        except IndexError:
          oldValue = 0
        result['oldValue'] = oldValue

      else: 
        # ok, that value is different from the opposite... store it to db
        voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", key)
        print >>sys.stderr, keyOpposite
        votes = voteQuery.fetch(1)
        try:
          vote = votes[0]
        except IndexError:
          vote = Vote(parent=userKey())
          vote.voteKey = req['key']
        vote.value = value
        vote.put()
        if value>0:
          result['status'] = "stored"
        else:
          result['status'] = "neutral"

      # send result to client
      self.response.out.write(json.dumps(result))

    else:
      #self.response.out.write(json.loads(self.request.body))
      self.error(403)

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/rpc', RPCHandler)],
                              debug=True)
