import sys
sys.path.append("..")
sys.path.append("../..")
import pika
import json
from common.logger import *
import sqlite3
from communications.request_handler import ServiceRequestHandler
import psycopg2
import psycopg2.extras
import datetime
import time

def setup_db_connection():
	conn = psycopg2.connect(host="localhost", database="players", user="postgres", password="coolumag")
	schema = (
		"""
		CREATE TABLE IF NOT EXISTS clan(
			id SERIAL PRIMARY KEY,
			name VARCHAR(30) NOT NULL,
			tag VARCHAR(4) NOT NULL
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS player_profile(
			id INTEGER PRIMARY KEY,
			username VARCHAR(12) NOT NULL,
			kills INTEGER DEFAULT 0,
			wins INTEGER DEFAULT 0,
			games INTEGER DEFAULT 0,
			clan INTEGER REFERENCES clan(id) ON DELETE SET NULL DEFAULT NULL,
			avatar VARCHAR(255) DEFAULT '',
			last_seen BIGINT DEFAULT 0
		);
		""" ,
		"""
		CREATE TABLE IF NOT EXISTS friend(
			player_id INTEGER REFERENCES player_profile(id),
			friend_id INTEGER REFERENCES player_profile(id),
			PRIMARY KEY(player_id, friend_id)
		);
		""" ,
		"""
		CREATE TABLE IF NOT EXISTS friend_invite(
			inviter_id INTEGER REFERENCES player_profile(id),
			invitee_id INTEGER REFERENCES player_profile(id),
			PRIMARY KEY(inviter_id, invitee_id)
		);
		"""
	)
	cursor = conn.cursor()
	for command in schema:
		cursor.execute(command)
	cursor.close()
	conn.commit()
	return conn

sql_conn = setup_db_connection()
times = []
cursor = sql_conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

def create_profile(user_id, username):
	log_info(f"Creating profile for user {id}")
	cursor.execute("INSERT INTO player_profile(id, username) VALUES(%s, %s)", (user_id, username))
	sql_conn.commit()

def get_user_by_id(id):
	#log_info(f"Retrieving profile for user {id}")
	#start_time = time.time_ns()
	cursor.execute("SELECT * FROM player_profile WHERE id=%s", (id,))
	result = cursor.fetchone()
	if result:
		return result
	return dict()

def get_user_by_name(username):
	log_info(f"Retrieving profile by name: {username}")
	cursor.execute("SELECT * FROM player_profile WHERE username=%s", (username,))
	a = cursor.fetchone()
	if a:
		return a
	else:
		return dict()

def get_friends_of_user(id):
	log_debug(f"Retrieving friends for user {id}")
	cursor.execute("SELECT friend_id FROM friend WHERE player_id = %s", (id,))
	return [f["friend_id"] for f in cursor.fetchall()]

def get_friend_invites_for_user(id):
	log_debug(f"Retrieving friend invites for user {id}")
	cursor.execute("SELECT inviter_id FROM friend_invite WHERE invitee_id = %s", (id,))
	return [f["inviter_id"] for f in cursor.fetchall()]

def add_friend_to_user(user_id, friend_id):
	log_debug(f"{user_id} added {friend_id} to friends :)")
	cursor.execute("INSERT INTO friend VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, friend_id))
	cursor.execute("INSERT INTO friend VALUES (%s, %s) ON CONFLICT DO NOTHING", (friend_id, user_id))
	sql_conn.commit()

def remove_friend_from_user(user_id, friend_id):
	log_debug(f"{user_id} removed {friend_id} from friends :(")
	cursor.execute("DELETE FROM friend WHERE player_id = %s AND friend_id = %s", (user_id, friend_id))
	cursor.execute("DELETE FROM friend WHERE player_id = %s AND friend_id = %s", (friend_id, user_id))
	sql_conn.commit()

def add_invite_to_user(invitee_id, inviter_id):
	log_debug(f"{invitee_id} received friend invite from {inviter_id}!")
	cursor.execute("INSERT INTO friend_invite VALUES (%s, %s) ON CONFLICT DO NOTHING", (inviter_id, invitee_id))
	sql_conn.commit()

def accept_friend_invite(user_id, inviter_id):
	log_debug(f"Friend invite for {user_id} by {inviter_id} accepted!")
	cursor.execute("SELECT 1 FROM friend_invite WHERE inviter_id = %s AND invitee_id = %s", (inviter_id, user_id))
	if cursor.fetchone():
		cursor.execute("DELETE FROM friend_invite WHERE inviter_id = %s AND invitee_id = %s", (inviter_id, user_id))
		add_friend_to_user(user_id, inviter_id)

def reject_friend_invite(user_id, inviter_id):
	log_debug(f"Friend invite for {user_id} by {inviter_id} rejected!")
	cursor.execute("DELETE FROM friend_invite WHERE inviter_id = %s AND invitee_id = %s", (inviter_id, user_id))
	sql_conn.commit()

def update_last_seen(user_id):
	log_debug(f"Updating last seen for {user_id}")
	cursor.execute("UPDATE player_profile SET last_seen = %s WHERE id = %s", (int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000), user_id))
	sql_conn.commit()


def on_request(msg):
	#print(time.time_ns())

	if msg["type"] == "get_profile":
		a = get_user_by_id(msg["id"])
		#times.append(time.time_ns() - start_time)
		#print(sum(times)/len(times))
		return a

	elif msg["type"] == "get_profile_by_name":
		return get_user_by_name(msg["name"])

	elif msg["type"] == "create_profile":
		create_profile(msg["id"], msg["username"])

	elif msg["type"] == "get_friends":
		return get_friends_of_user(msg["id"])

	elif msg["type"] == "get_friend_invites":
		return get_friend_invites_for_user(msg["id"])

	elif msg["type"] == "invite_friend":
		add_invite_to_user(msg["invitee"], msg["inviter"])

	elif msg["type"] == "accept_friend_invite":
		accept_friend_invite(msg["invitee"], msg["inviter"])

	elif msg["type"] == "reject_friend_invite":
		reject_friend_invite(msg["invitee"], msg["inviter"])

	elif msg["type"] == "remove_friend":
		remove_friend_from_user(msg["remover"], msg["removee"])

	elif msg["type"] == "id_online" or msg["type"] == "id_offline":
		update_last_seen(msg["id"])

	else:
		raise Exception("UNHANDLED MESSAGE: " + str(msg))

rrh = ServiceRequestHandler("profiles", "profile_queue", on_request, broadcasts=["presence"])
rrh.run()
