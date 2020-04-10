from common.lazy import LazyPlayer
from agw.models import Player

class LazyPlayerConverter:
	regex = '[0-9]+'

	def to_python(self, value):
		return LazyPlayer(int(value), precached_username=Player.objects.get(pk=value).username)

	def to_url(self, value):
		return str(value.pk)
