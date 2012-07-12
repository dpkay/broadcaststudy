import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import yaml
import json

from google.appengine.ext import db
from google.appengine.api import users

from protorpc import messages
from protorpc.wsgi import service
from protorpc import remote

jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))


class TaskDict(dict):
  def __init__(self):
    with file('tasks.yaml', 'r') as stream:
      for item in yaml.load(stream):
        self[item['name']] = item


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

        # initialize task
        taskdict = TaskDict()

        # read votes from db and augment task dictionary
        votesQuery = Vote.all().ancestor(userKey())
        votes = votesQuery.fetch(100)
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
      if value > 0: 
        result = {"status": "stored"}
      else:
        result = {"status": 0}

      voteQuery = Vote.all().ancestor(userKey()).filter("voteKey = ", req['key'])
      votes = voteQuery.fetch(1)
      try:
        vote = votes[0]
      except IndexError:
        vote = Vote(parent=userKey())
        vote.voteKey = req['key']
      vote.value = value
      vote.put()

      self.response.out.write(json.dumps(result))
    else:
      #self.response.out.write(json.loads(self.request.body))
      self.error(403)

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/rpc', RPCHandler)],
                              debug=True)
