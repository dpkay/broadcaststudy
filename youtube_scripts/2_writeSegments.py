import yaml
import sys
import re
from collections import defaultdict

segments = defaultdict(dict)

rawClipList = yaml.load(sys.stdin.read())
for rawClip in rawClipList:
  pattern = r'^.*disney(\d).*(\d\d\d)$'
  result = re.match(pattern, rawClip['title'])
  groups = result.groups()
  camera = int(groups[0])
  segment = int(groups[1])

  pattern = r'.*youtube.com\/v\/(.*)\?.*'
  result = re.match(pattern, rawClip['url'])
  groups = result.groups()
  youtube_id = groups[0]
  segments[segment][camera] = youtube_id

print yaml.dump(dict(segments))
