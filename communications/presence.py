import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.rpc import RPCClient
from common.utils import convert_to_pk

__rpc = RPCClient("presence_queue")

@convert_to_pk
def is_online(id):
	return __rpc.request({"type": "is_online", "id": id})
