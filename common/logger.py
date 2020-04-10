import pika
from inspect import getframeinfo, stack
import time
import os

__channel = None


def __init():
	global __channel
	if __channel:
		return
	#__connection = pika.BlockingConnection(pika.URLParameters('amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'))
	__connection = pika.BlockingConnection(
	    pika.URLParameters('amqp://guest:guest@localhost/'))
	__channel = __connection.channel()
	__channel.exchange_declare(exchange='logs', exchange_type='fanout')


__init()


def __send_log(level, message):
	global __channel
	try:
		caller = getframeinfo(stack()[2][0])
	except:
		caller = None
	asctime = time.strftime("%d-%m-%Y %H:%M:%S")
	if caller:
		body = f"[{asctime}] {level}: {os.path.normpath(os.path.basename(caller.filename))}({caller.lineno}): {message}"
	else:
		body = f"[{asctime}] {level}: ???: {message}"
	while True:
		try:
			__channel.basic_publish(exchange='logs', routing_key='', body=body)
		except pika.exceptions.AMQPConnectionError as e:
			print(e)
			__channel = None
			__init()
			continue
		break


def log_debug(message):
	__send_log("DEBUG", message)


def log_info(message):
	__send_log("INFO", message)


def log_warning(message):
	__send_log("WARNING", message)


def log_error(message):
	__send_log("ERROR", message)


def log_critical(message):
	__send_log("CRITICAL", message)
