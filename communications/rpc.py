import pika
import uuid
import json
from retry import retry
import threading
from functools import partial
import time
from typing import *


class RPCTimeout(Exception):
	pass


class RPCRequest:
	def __init__(self, rpc, corr_id):
		self.rpc = rpc
		self.corr_id = corr_id

	def recv(self):
		return self.rpc._recv(self.corr_id)

	def resolve(self):
		return self.recv()

	def __bool__(self):
		raise Exception("TRYING TO USE RPC REQUEST WITHOUT RESOLVING IT!!")


class RPCClient:
	def __init__(self, key, timeout=10):
		self.connection = None
		self.channel = None

		self.key = key
		self.responses = {}
		self.response_events = {}
		self.conn_thread = None
		self.connection_thread = threading.Thread(target=self.connect)
		self.connection_thread.setDaemon(True)
		self.connection_thread.start()
		self.threads = set()
		self.timeout = timeout

	@retry(pika.exceptions.AMQPConnectionError, delay=1, jitter=(1, 3))
	def connect(self):
		print("Connecting to rabbitmq")
		#if self.connection and self.connection.is_open:
		#	self.connection.close()
		#if self.channel and self.channel.is_open:
		#	self.channel.close()
		self.connection = pika.BlockingConnection(
		    #pika.URLParameters('amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'))
		    pika.URLParameters('amqp://guest:guest@localhost/'))

		self.channel = self.connection.channel()

		result = self.channel.queue_declare(queue='',
		                                    auto_delete=True,
		                                    exclusive=True)
		self.callback_queue = result.method.queue

		self.channel.basic_consume(queue=self.callback_queue,
		                           on_message_callback=self.on_response,
		                           auto_ack=True)
		self.channel.start_consuming()

	def on_response(self, ch, method, props, body):
		self.responses[props.correlation_id] = json.loads(body)
		self.response_events[props.correlation_id].set()

	def __publish(self, msg, corr_id=None):
		if corr_id:
			self.channel.basic_publish(exchange='',
			                           routing_key=self.key,
			                           properties=pika.BasicProperties(
			                               reply_to=self.callback_queue,
			                               correlation_id=corr_id,
			                               delivery_mode=1),
			                           body=msg)
			#print(time.time_ns())
		else:
			self.channel.basic_publish(
			    exchange='',
			    routing_key=self.key,
			    body=msg,
			    properties=pika.BasicProperties(delivery_mode=1))

	def request(self, msg: Union[Dict, str]) -> RPCRequest:
		if self.key is None:
			raise Exception("Using base RPC with no profile")
		corr_id = str(uuid.uuid4())
		if type(msg) is dict:
			msg = json.dumps(msg)
		self.response_events[corr_id] = threading.Event()
		self.threads.add(threading.currentThread().ident)
		self.connection.add_callback_threadsafe(
		    partial(self.__publish, msg, corr_id))
		return RPCRequest(self, corr_id)

	def request_forget(self, msg):
		if self.key is None:
			raise Exception("Using base RPC with no profile")
		if type(msg) is dict:
			msg = json.dumps(msg)
		self.connection.add_callback_threadsafe(partial(self.__publish, msg))

	def _recv(self, corr_id):
		if not self.response_events[corr_id].wait(self.timeout):
			raise RPCTimeout
		self.response_events.pop(corr_id)
		return self.responses.pop(corr_id)


def resolve(requests) -> Any:
	if isinstance(requests, list):
		res = []
		for req in requests:
			res.append(req.resolve())
		return res
	else:
		return requests.resolve()
