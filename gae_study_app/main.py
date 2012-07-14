import re
import collections
import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import yaml
import json
import sys
import random
import operator

from google.appengine.ext import db
from google.appengine.api import users

from protorpc import messages
from protorpc.wsgi import service
from protorpc import remote

from webapp2_extras import auth 
from webapp2_extras import sessions
from webapp2_extras.appengine.auth import models

distinguishedIndexes = [40, 80, 120, 160, 190,
                        240, 280, 320, 360, 400]

jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


class SegmentDict(dict):
  def __init__(self, filename):
    with file(filename, 'r') as stream:
      super(SegmentDict, self).__init__(yaml.load(stream))

class Vote(db.Model):
  voteKey = db.StringProperty()
  cameraName = db.StringProperty()

class Metavote(db.Model):
  voteKey = db.StringProperty()
  value = db.StringProperty()

def userId():
  user = users.get_current_user()
  if user:
    return user.user_id()
  else:
    return 0


def userKey(user_id_cmd=userId):
  return db.Key.from_path('User', user_id_cmd())


def userName():
  return users.get_current_user().nickname()


class BaseHandler(webapp2.RequestHandler):
    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            super(BaseHandler, self).dispatch()
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()


class StatsHandler(BaseHandler):
    def get(self):
      voteQuery = Vote.all()
      votes = voteQuery.fetch(9999)
      segments = collections.defaultdict(lambda: collections.defaultdict(int))
      for vote in votes:
        result = re.match('segment(\d\d\d)_(.*)', vote.voteKey).groups()
        if result[1] == 'best':
          increment = +1
        elif result[1] == 'worst':
          increment = -1
        segments[result[0]][vote.cameraName] += increment

      # split and convert to normal dict
      normalSegments = []
      distinguishedSegments = []
      for key, value in segments.iteritems():

        # force creation of keys
        value['A']
        value['B']
        value['C']

        value = dict(value)
        value['id'] = int(key)
        if int(key) in distinguishedIndexes:
          distinguishedSegments.append(value)
        else:
          normalSegments.append(value)

      template_values = {
          'distinguishedSegments': distinguishedSegments,
          'normalSegments': normalSegments
      }
      template = jinja_environment.get_template('stats_template.html')
      self.response.out.write(template.render(template_values))

class StudyHandler(BaseHandler):
    def get(self):
        if users.get_current_user():
          #logout_url = users.create_logout_url(self.request.uri)
          logout_url = "/logout"
        else:
          self.redirect(users.create_login_url(self.request.uri))
          return

        print >>sys.stderr,userId(),userKey()
        random.seed(userId())

        # initialize segments
        #distinguishedSegments = SegmentDict('distinguished_segments.yaml')
        segments = SegmentDict('segments.yaml')

        normalIndexes = set(segments.keys()) - set(distinguishedIndexes)
        #distinguishedSegments = {}
        #for i in distinguishedIndexes:
        #  distinguishedSegments[i] = allSegments[i]

        chosenIndexes = random.sample(distinguishedIndexes, 10) +\
                        random.sample(normalIndexes, 0)

        taskdict = {}
        #for key, data in distinguishedSegments.iteritems():
        for index in chosenIndexes:
          data = segments[index]
           
          prettyPrefix = 'D' if index in distinguishedIndexes else 'N'
          name = 'segment%03d' % index 
          task = {}
          task['prettyName'] = prettyPrefix + str(index)
#          name = task['prettyName']
          task['name'] = name
          task['index'] = index

          shuffledIds = ['A','B','C']
          random.shuffle(shuffledIds)
          task['youtube_id1'] = data[shuffledIds[0]]
          task['youtube_id2'] = data[shuffledIds[1]]
          task['youtube_id3'] = data[shuffledIds[2]]
          task['camera1'] = shuffledIds[0]
          task['camera2'] = shuffledIds[1]
          task['camera3'] = shuffledIds[2]
          taskdict[name] = task

        metataskDict = {
        'photo_experience': {
          'name': 'photo_experience',
          'label': 'How would you rate your experience in either photography or film editing?',
          'choices': [('0','None'),
                      ('1','Basic'),
                      ('2','Hobbyist'),
                      ('3','Serious hobbyist'),
                      ('4','Professional')],
           'selected': 'X'
        },
        'watch_experience': {
          'name': 'watch_experience',
          'label': 'How often do you watch live sports on TV/computer?',
          'choices': [('0','Never'),
                      ('1','Multiple times<br/> per year'),
                      ('2','Multiple times<br/> per month'),
                      ('3','Multiple times<br/> per week'),
                      ('4','Daily')],
           'selected': 'X'
        },
        }

        # read votes from db and augment task dictionary
        votesQuery = Vote.all().ancestor(userKey())
        votes = votesQuery.fetch(500)
        for vote in votes:
          taskName, suffix = vote.voteKey.split('_') 
          taskdict[taskName]['selected_%s' % suffix] = vote.cameraName

        metavotesQuery = Metavote.all().ancestor(userKey())
        metavotes = metavotesQuery.fetch(50)
        for vote in metavotes:
          metataskDict[vote.voteKey]['selected'] = vote.value

        # we can now throw away the keys, so
        # convert augmented task dictionary to list.
        tasks = taskdict.values()
        random.shuffle(tasks)

        template_values = {
          'username': '%s (%s, %s)' % (self.session.get('nickname'),
                                       self.session.get('age'),
                                       self.session.get('gender')),
          'logout_url': logout_url,
          'tasks': tasks,
          'metatasks': metataskDict.values()
        }
        template = jinja_environment.get_template('voting_template.html')
        self.response.out.write(template.render(template_values))


class RPCHandler(BaseHandler):
  def post(self):
    req = json.loads(self.request.body)
    action = req['action']
    if action == "metavote":
      value = req['value']
      if value != 'X':
        result = {'status': 'stored'}
      else:
        result = {'status': 'neutral'}

      key = req['key']
      voteQuery = Metavote.all().ancestor(userKey()).filter("voteKey = ", key)
      votes = voteQuery.fetch(1)
      try:
        vote = votes[0]
      except IndexError:
        vote = Metavote(parent=userKey())
        vote.voteKey = req['key']
      vote.value = value
      vote.put()

      # send result to client
      self.response.out.write(json.dumps(result))

    elif action == "vote":
      valueSplit = req['value'].split('_')
      radioValue = valueSplit[0]
      cameraName = valueSplit[1]
      result = {'status': 'undefined'}

      # test whether opposite has same value. if yes then fail
      key = req['key']
      keySplit = req['key'].split('_')
      keyOpposite = keySplit[0] + '_' + ('best' if keySplit[1] == 'worst' else 'worst')
      voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", keyOpposite)
      votes = voteQuery.fetch(1)
      if radioValue>0 and len(votes)>0 and votes[0].cameraName == cameraName:
        # don't allow best and worst to have the same value
        result['status'] = "failed"

        # jump back to old value
        result['oldValue'] = 0
        cameraName = 'X'

      else: 
        # ok, that value is different from the opposite... give a nice result
        if cameraName != 'X':
          result['status'] = "stored"
        else:
          result['status'] = "neutral"

      voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", key)
      votes = voteQuery.fetch(1)
      try:
        vote = votes[0]
      except IndexError:
        vote = Vote(parent=userKey())
        vote.voteKey = req['key']
      vote.cameraName = cameraName
      vote.put()

      # send result to client
      self.response.out.write(json.dumps(result))

    else:
      #self.response.out.write(json.loads(self.request.body))
      self.error(403)


class LoginHandler(BaseHandler):
  def get(self):
      if (self.session.get('nickname') != None and
          self.session.get('nickname') != None and
          self.session.get('nickname') != None):
          self.redirect('/study')

      else:
        template_values = {
          'myfoo': self.session.get('nickname')
        }
        self.session['foo']='barxxasdf'
        template = jinja_environment.get_template('login_template.html')
        self.response.out.write(template.render(template_values))

  def post(self):
      self.session['nickname'] = self.request.get('nickname')
      self.session['age'] = self.request.get('age')
      self.session['gender'] = self.request.get('gender')
      self.redirect('/')


class LogoutHandler(BaseHandler):
  def get(self):
    del self.session['nickname'] 
    del self.session['age'] 
    del self.session['gender'] 
    self.redirect('/')

app = webapp2.WSGIApplication([('/', LoginHandler),
                               ('/study', StudyHandler),
                               ('/rpc', RPCHandler),
                               ('/logout', LogoutHandler),
                               ('/stats', StatsHandler)],
                              debug=True,
                              config={
                                'webapp2_extras.sessions':
                                {
                                  'secret_key': 'jflmcgsdljkghdflsjgkhsm'
                                }
                              })
