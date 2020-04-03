import pika
from aio_pika import connect, IncomingMessage, Exchange, Message, ExchangeType
import json
import asyncio
from common.logger import *
from functools import partial
from retry import retry

class ServiceRequestHandler:
	def __init__(self, name, keys, callback, custom_json_encoder=None, broadcasts=[]):
		self.name = name
		if isinstance(keys, str):
			self.keys = [keys]
		elif not keys:
			self.keys = []
		else:
			self.keys = keys
		self.callback = callback
		self.custom_json_encoder = custom_json_encoder
		self.broadcasts = broadcasts

	def on_message(self, ch, method, props, body):
		body = json.loads(body)
		log_debug(f"Message received by {self.name}: {body}")
		response = self.callback(body)
		if response is None:
			response = dict()
		if props.reply_to:
			log_debug(f"{self.name} responding with: {response}")
			if self.custom_json_encoder:
				response = bytes(json.dumps(response, cls=self.custom_json_encoder), "utf8")
			else:
				response = bytes(json.dumps(response), "utf8")
			ch.basic_publish(exchange='',
							routing_key=props.reply_to,
							properties=pika.BasicProperties(correlation_id = props.correlation_id, delivery_mode=1),
							body=response)
		ch.basic_ack(delivery_tag=method.delivery_tag)

	@retry(pika.exceptions.AMQPConnectionError, delay=1, jitter=(1,3))
	def run(self):
		connection = pika.BlockingConnection(
			#pika.URLParameters('amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'))
			pika.URLParameters('amqp://guest:guest@localhost/'))
		channel = connection.channel()
		channel.basic_qos(prefetch_count=5)

		for i, key in enumerate(self.keys):
			state = channel.queue_declare(queue=key)
			if i == 0:
				self.name += "-"+str(state.method.consumer_count+1)
			channel.basic_consume(queue=key, on_message_callback=self.on_message)

		result = channel.queue_declare(queue='', exclusive=True, auto_delete=True)
		for exchange in self.broadcasts:
			channel.exchange_declare(exchange, exchange_type="fanout")
			channel.queue_bind(exchange=exchange, queue=result.method.queue)
			channel.basic_consume(queue=result.method.queue, on_message_callback=self.on_message)

		log_info(f"{self.name} starting.")
		try:
			channel.start_consuming()
		except KeyboardInterrupt:
			channel.stop_consuming()
		connection.close()

class AsyncServiceRequestHandler:
	def __init__(self, name, keys, callback, custom_json_encoder=None, broadcasts=[]):
		self.name = name
		if isinstance(keys, str):
			self.keys = [keys]
		elif not keys:
			self.keys = []
		else:
			self.keys = keys
		self.callback = callback
		self.custom_json_encoder = custom_json_encoder
		self.broadcasts = broadcasts

	async def on_message(self, exchange, msg):
		body = json.loads(msg.body)
		log_debug(f"Message received by {self.name}: {body}")
		response = await self.callback(body)
		if response is None:
			response = dict()
		if msg.reply_to:
			log_debug(f"{self.name} responding with: {response}")
			if self.custom_json_encoder:
				response = bytes(json.dumps(response, cls=self.custom_json_encoder), "utf8")
			else:
				response = bytes(json.dumps(response), "utf8")

			await exchange.publish(
				Message(
					body=response,
					correlation_id=msg.correlation_id
				),
				routing_key=msg.reply_to
			)

	async def run(self):
		connection = await connect(
			#'amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'
			'amqp://guest:guest@localhost/'
		)
		channel = await connection.channel()
		for i, key in enumerate(self.keys):
			queue = await channel.declare_queue(key)
			if i == 0:
				self.name += "-"+str(queue.declaration_result.consumer_count+1)
			await queue.consume(partial(self.on_message, channel.default_exchange))

		queue = await channel.declare_queue(exclusive=True, auto_delete=True)
		for exchange in self.broadcasts:
			ex = await channel.declare_exchange(exchange, ExchangeType.FANOUT)
			await queue.bind(exchange)
			await queue.consume(partial(self.on_message, ex))
		log_info(f"{self.name} starting.")
		print("bebns")
