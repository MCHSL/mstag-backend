import pika
import uuid
import json
from typing import *


class Broadcaster:
	def __init__(self):
		self.connect()

	def connect(self):
		#self.connection = pika.BlockingConnection(pika.URLParameters('amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'))
		self.connection = pika.BlockingConnection(
		    pika.URLParameters('amqp://guest:guest@localhost/'))
		self.channel = self.connection.channel()

	def broadcast(self, exchange: str, body: Union[Dict, str]):
		if isinstance(body, dict):
			body = json.dumps(body)
		while True:
			try:
				self.channel.exchange_declare(exchange=exchange,
				                              exchange_type='fanout')
				self.channel.basic_publish(exchange=exchange,
				                           routing_key='',
				                           body=body)
				break
			except pika.exceptions.AMQPConnectionError as e:
				print("Broadcaster error: " + str(e))
				self.connect()


__broadcaster = Broadcaster()


def broadcast(exchange, body):
	__broadcaster.broadcast(exchange, body)
