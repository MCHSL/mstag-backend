import pika

connection = pika.BlockingConnection(
    #pika.URLParameters('amqp://ccceuqky:aPYn9wF8CZe6f0VgBWtvpmqA0kvx_Gqz@hare.rmq.cloudamqp.com/ccceuqky'))
	pika.URLParameters('amqp://guest:guest@localhost/'))
channel = connection.channel()

channel.exchange_declare(exchange='logs', exchange_type='fanout')

result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='logs', queue=queue_name)

print(' [*] Waiting for logs. To exit press CTRL+C')

def callback(ch, method, properties, body):
    print(body.decode("utf8"))

channel.basic_consume(
    queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()
