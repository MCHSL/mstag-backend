import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.rpc import RPCClient

__rpc = RPCClient("auth_queue")

def get_id_from_token(token):
	return __rpc.request({"type": "get_id_from_token", "token": token})
