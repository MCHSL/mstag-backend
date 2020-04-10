from communications import team
from communications import profile
from communications import presence
from communications.rpc import resolve
import datetime
import time
from django.http import Http404
from typing import *
from typing_extensions import TypedDict


class PlayerProfile(TypedDict):
	username: str
	avatar: str
	kills: int
	wins: int
	games: int
	last_seen: float
	clan: Any


def now():
	return int(
	    datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


class LazyPlayerListIterator:
	def __init__(self, player_list):
		self.player_list = player_list
		self.index = 0

	def __iter__(self):
		return self

	def __next__(self):
		try:
			p = self.player_list[self.index]
			self.index += 1
			return p
		except IndexError:
			raise StopIteration


class LazyPlayerList:
	def __init__(self, players, on_add_element=None, on_remove_element=None):
		self.players: List[Union[int,
		                         LazyPlayer]] = players  # list of Player pk's
		self.on_add_element = on_add_element
		self.on_remove_element = on_remove_element

	def __getitem__(self, key):
		p = self.players[key]
		if isinstance(p, LazyPlayer):
			return p
		elif isinstance(p, int):  #Player pk
			self.players[key] = LazyPlayer(p)
			return self.players[key]
		else:
			raise TypeError(p)

	def __setitem__(self, key, value):
		raise NotImplementedError

	def __iter__(self):
		return LazyPlayerListIterator(self)

	def __contains__(self, obj):
		print(self.players)
		print(obj.pk)
		for p in self.players:
			if p == obj:
				return True
		return False


class LazyTeam:
	def __init__(self, pk):
		self.__nonexistent = False
		self.__last_lookup = 0

		if isinstance(pk, int):
			self.pk = pk
		elif hasattr(pk, "pk"):
			self.pk = pk.pk
		elif isinstance(pk, dict):
			self._members = pk["members"]
			self._invitees = pk["invitees"]
			self._leader = pk["leader"]
			self.pk = pk["pk"]
			self.__last_lookup = time.time()
		elif pk is None:
			self.pk = -1
			self.__nonexistent = True
		else:
			raise TypeError

	def __get_info(self):
		if time.time() - self.__last_lookup < 1 or self.__nonexistent:
			return
		self.__last_lookup = time.time()
		info = resolve(team.get_team(self.pk))
		if info is None:
			self.__nonexistent = True
			return
		self._members = info["members"]
		self._invitees = info["invitees"]
		self._leader = info["leader"]

	def __bool__(self):
		self.__get_info()
		return not self.__nonexistent

	@property
	def members(self):
		self.__get_info()
		return LazyPlayerList(self._members)

	@property
	def invitees(self):
		self.__get_info()
		return LazyPlayerList(self._invitees)

	@property
	def leader(self):
		self.__get_info()
		return LazyPlayer(self._leader)

	def member_pks(self):
		self.__get_info()
		return self._members

	def invite(self, player):
		self.__last_lookup = 0
		team.invite_player_to_team(player, self)


class LazyPlayer:
	def __init__(self, pk: int, precached_username: str = ""):
		self.pk: int = pk

		self._last_basic_lookup: float = 0
		self._last_friends_lookup: float = 0
		self._last_friend_invite_lookup: float = 0
		self._last_team_lookup: float = 0

		self._username: str = precached_username
		self._kills: int = 0
		self._wins: int = 0
		self._games: int = 0
		self._clan: Any = None
		self._avatar: str = ""
		self._last_seen: float = 0

		self._friends: Optional[LazyPlayerList] = None
		self._friend_invites: Optional[LazyPlayerList] = None
		self._team: Optional[LazyTeam] = None

	def __get_basic_info(self):
		if time.time() - self._last_basic_lookup < 1:
			return
		self._last_basic_lookup = time.time()
		prof: PlayerProfile = resolve(profile.request_profile(self.pk))
		if not prof:
			raise Http404("Profile does not exist")
		self._username = prof["username"]
		self._kills = prof["kills"]
		self._wins = prof["wins"]
		self._games = prof["games"]
		self._clan = prof["clan"]  #Add a LazyClan once clans are added
		self._avatar = prof["avatar"]
		self._last_seen = prof["last_seen"]

	def __get_friends(self):
		if time.time() - self._last_friends_lookup < 1:
			return
		self._last_friends_lookup = time.time()
		friends = resolve(profile.get_friends(self.pk))
		self._friends = LazyPlayerList(friends)

	def __get_friend_invites(self):
		if time.time() - self._last_friend_invite_lookup < 1:
			return
		self._last_friend_invite_lookup = time.time()
		invites = resolve(profile.get_friend_invites(self.pk))
		self._friend_invites = LazyPlayerList(invites)

	@property
	def username(self) -> str:
		if not self._username:
			self.__get_basic_info()
		return self._username

	@property
	def kills(self) -> int:
		self.__get_basic_info()
		return self._kills

	@property
	def wins(self) -> int:
		self.__get_basic_info()
		return self._wins

	@property
	def games(self) -> int:
		self.__get_basic_info()
		return self._games

	@property
	def avatar(self) -> str:
		self.__get_basic_info()
		return self._avatar

	@property
	def clan(self) -> Any:
		self.__get_basic_info()
		return self._clan

	@property
	def last_seen(self) -> float:
		self.__get_basic_info()
		return self._last_seen

	@property
	def last_seen_delta(self) -> float:
		return (now() - self.last_seen) / 1000

	@property
	def friends(self) -> Optional[LazyPlayerList]:
		self.__get_friends()
		return self._friends

	@property
	def friend_invites(self) -> Optional[LazyPlayerList]:
		self.__get_friend_invites()
		return self._friend_invites

	@property
	def team(self) -> Optional[LazyTeam]:
		if self._team and time.time() - self._last_team_lookup < 1:
			return self._team
		t = resolve(team.get_team_for_player(self.pk))
		if t is None:
			return t
		self._team = LazyTeam(t)
		return self._team

	def create_team(self) -> LazyTeam:
		if self._team and time.time() - self._last_team_lookup < 1:
			return self._team
		self._team = LazyTeam(team.get_or_create_team(self.pk))
		return self._team

	@property
	def online(self) -> bool:
		return resolve(presence.is_online(self.pk))

	def notify(self, typ: str, **kwargs) -> None:
		from communications.notifications import send_notification
		send_notification(self.pk, typ, **kwargs)

	def chat_global(self, msg: str) -> None:
		from communications.chat import send_global_chat_message, send_team_chat_message
		send_global_chat_message(self, msg)

	def chat_team(self, msg: str) -> None:
		from communications.chat import send_global_chat_message, send_team_chat_message
		send_team_chat_message(self, msg)

	def __eq__(self, other):
		if isinstance(other, str):
			other = int(other)
		if isinstance(other, int):
			return self.pk == other
		elif isinstance(other, LazyPlayer):
			return self.pk == other.pk
		else:
			raise TypeError


LazyPlayerEquivalent = Union[LazyPlayer, int]
