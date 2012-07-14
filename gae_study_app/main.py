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

from protorpc import messages
from protorpc.wsgi import service
from protorpc import remote

from webapp2_extras import sessions

from google.appengine.ext import db

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


class BaseHandler(webapp2.RequestHandler):
    def userId(self):
      return '%s__%s__%s' % (self.session.get('nickname'),
                             self.session.get('age'),
                             self.session.get('gender'))
    def userKey(self):
      return db.Key.from_path('User', self.userId())

    def userName(self):
      return self.session.get('nickname')

    def hasUserKey(self):
      return (self.session.get('nickname') != None and
              len(self.session.get('nickname')) > 0 and
              self.session.get('age') != None and
              len(self.session.get('age')) > 0 and
              int(self.session.get('age')) > 0 and
              self.session.get('gender') != None and
              self.session.get('gender') in ['m', 'f'])

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
      parentKeys = collections.defaultdict(int)
      for vote in votes:
        result = re.match('segment(\d\d\d)_(.*)', vote.voteKey).groups()
        if result[1] == 'best':
          increment = +1
        elif result[1] == 'worst':
          increment = -1
        segments[result[0]][vote.cameraName] += increment
        parentKeys[vote.parent_key()] += 1

      # get nice user list
      users = []
      for key, count in parentKeys.items():
        user = {}
        (user['nickname'],
         user['age'],
         user['gender']) = key.name().split('__')
        user['votes'] = count
        metavoteQuery = Metavote.all().ancestor(key)
        metavotes = metavoteQuery.fetch(10)
        metavoteDict = { m.voteKey:m.value for m in metavotes }
        user = dict(user, **metavoteDict)
        users.append(user)


      # split and convert to normal dict
      normalSegments = []
      distinguishedSegments = []
      for key, value in sorted(segments.items()):

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
          'normalSegments': normalSegments,
          'users': users
      }
      template = jinja_environment.get_template('stats_template.html')
      self.response.out.write(template.render(template_values))

class StudyHandler(BaseHandler):
    def get(self):
        if not self.hasUserKey():
          self.redirect('/')

        random.seed(self.userId())

        # initialize segments
        #distinguishedSegments = SegmentDict('distinguished_segments.yaml')
        segments = SegmentDict('segments.yaml')

        normalIndexes = set(segments.keys()) - set(distinguishedIndexes)
        #distinguishedSegments = {}
        #for i in distinguishedIndexes:
        #  distinguishedSegments[i] = allSegments[i]

        chosenIndexes = random.sample(distinguishedIndexes, 5) +\
                        random.sample(normalIndexes, 25)

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
        votesQuery = Vote.all().ancestor(self.userKey())
        votes = votesQuery.fetch(500)
        for vote in votes:
          taskName, suffix = vote.voteKey.split('_') 
          taskdict[taskName]['selected_%s' % suffix] = vote.cameraName

        metavotesQuery = Metavote.all().ancestor(self.userKey())
        metavotes = metavotesQuery.fetch(50)
        for vote in metavotes:
          metataskDict[vote.voteKey]['selected'] = vote.value

        # we can now throw away the keys, so
        # convert augmented task dictionary to list.
        tasks = taskdict.values()
        random.shuffle(tasks)

        template_values = {
          'username': self.userName(),
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
      voteQuery = Metavote.all().ancestor(self.userKey()).filter("voteKey = ", key)
      votes = voteQuery.fetch(1)
      try:
        vote = votes[0]
      except IndexError:
        vote = Metavote(parent=self.userKey())
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
      voteQuery = Vote.all().ancestor(self.userKey()).filter("voteKey = ", keyOpposite)
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

      voteQuery = Vote.all().ancestor(self.userKey()).filter("voteKey = ", key)
      votes = voteQuery.fetch(1)
      try:
        vote = votes[0]
      except IndexError:
        vote = Vote(parent=self.userKey())
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
      if (self.hasUserKey()):
          self.redirect('/study')

      else:
        template_values = { }
        template = jinja_environment.get_template('login_template.html')
        self.response.out.write(template.render(template_values))

  def post(self):
      self.session['nickname'] = self.request.get('nickname')
      self.session['age'] = self.request.get('age')
      self.session['gender'] = self.request.get('gender')
      self.redirect('/')


class LogoutHandler(BaseHandler):
  def get(self):
    if not self.hasUserKey():
      self.redirect('/')
    self.session['nickname'] = None
    self.session['age'] = None
    self.session['gender'] = None
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
