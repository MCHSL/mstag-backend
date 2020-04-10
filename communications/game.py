import sys

from communications.rpc import RPCClient

sys.path.append("..")


__rpc = RPCClient("game_queue")

def reserve_lobby(players):
	pids = []
	for player in players:
		if isinstance(player, int):
			pids.append(player)
		else:
			pids.append(player.pk)
	return __rpc.request({"type": "reserve_lobby", "ids": pids})
