import json
import sys
import uuid

import pika

from communications.rpc import RPCClient, RPCRequest

sys.path.append("..")

__rpc = RPCClient("auth_queue")


def get_id_from_token(token: str) -> RPCRequest:
	return __rpc.request({"type": "get_id_from_token", "token": token})
