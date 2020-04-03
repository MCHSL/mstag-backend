import requests
import time
import sys

s = requests.Session()
t = time.time()
i = 1
c = 0
while True:
	s.get("http://127.0.0.1:8000/api/v1/user/1/")
	c += 1
	i += 1
	if i % 100 == 0:
		i = 1
		sys.stdout.write(str(c / (time.time() - t))+"\r")
		sys.stdout.flush()
		c = 1
		t = time.time()
