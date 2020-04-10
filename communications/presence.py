import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.rpc import RPCClient, RPCRequest
from common.utils import convert_to_pk

__rpc = RPCClient("presence_queue")


@convert_to_pk
def is_online(id: int) -> RPCRequest:
	return __rpc.request({"type": "is_online", "id": id})
