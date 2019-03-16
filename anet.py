"""

ANet: a platform to distribute commands over the computers in the KUL department of computer science (building A) through SSH (using public key authentication without passphrases).

Made by Wouter Baert, with some ssh/rsync/nc-commands from Maarten Baert.

Usage:

anet <batch-file> [dependencies]
batch-file: Path to the text file containing the batch requests. The batch file consists of requests, each represented by one command on one line. The ID of each request is its index (zero-based).
dependencies: Path containing all dependencies necessary for execution. If this is a folder, should end with /.

Response is returned as a 4-byte little-endian integer describing the request ID, followed by a 4-byte little-endian integer describing the response length in bytes, followed by the response (all binary data).

"""

# IMPORTANT: If client process doesn't receive any new responses, make sure to turn printing off, may fill stderr buffer and block ANet.

"""

Internal protocol (all integers are 4-byte little-endian):

Sending messages
- int: indicates message type (0: new command, 1: kill command)
For new command:
- int: request_id
- int: length of command string
- string: command string
For kill command:
- int: request_id

Receiving messages
- int: request_id
- int: length of response (-1 indicates a crash, no response)
- bytes: response
"""

import sys
from subprocess import Popen, PIPE
from select import epoll, EPOLLIN, EPOLLERR, EPOLLHUP
import struct
from time import time, sleep

start = time()

# Constants
student_id = "r0597343"
printing = False
hosts = ("aalst", "aarlen", "alken", "amay", "andenne", "ans", "asse", "aubel", "bastogne", "bergen", "beringen", "beveren", "bilzen", "binche", "borgworm", "brugge", "charleroi", "ciney", "couvin", "damme", "diest", "dilbeek", "dinant", "doornik", "durbuy", "eeklo", "eupen", "fleurus", "geel", "genk", "gent", "gouvy", "haacht", "halle", "ham", "hamme", "hasselt", "hastiere", "heist", "herent", "herstal", "hoei", "ieper", "jemeppe", "kaprijke", "knokke", "komen", "kortrijk", "lanaken", "libin", "lier", "lint", "luik", "maaseik", "malle", "marche", "mechelen", "mol", "namen", "nijvel", "ninove", "ohey", "orval", "overpelt", "peer", "perwez", "pittem", "seraing", "stavelot", "terhulpen", "tienen", "tubize", "turnhout", "verviers", "vielsalm", "vilvoorde", "virton", "voeren", "waterloo", "waver", "zwalm") # 81 machines, 324 cores
processes_per_host = 4
max_connections_attempts = 10
reconnect_delay = 0.01
magic_string = "anet_dispatcher started successfully."

# Functions

def open_connection(host, attempts, connections, poll_object):
	
	# Opens a new connection, registers it with the poll_object and adds it to connections
	
	if printing:
		sys.stderr.write("Opening connection at %s to %s, attempt %s\n"%(time() - start, host, attempts))
		sys.stderr.flush()
	
	p = Popen(["ssh", "-o", "ProxyCommand ssh -q cs nc " + host + ".cs.kotnet.kuleuven.be 22", "%s@cs-"%student_id + host, "python3 /home/%s/anet/src/anet_dispatcher.py"%student_id], bufsize=0, stdin=PIPE, stdout=PIPE)
	connections[p.stdout.fileno()] = {
		"process": p,
		"host": host,
		"attempts": attempts,
		"request_ids": []
	}
	poll_object.register(p.stdout, eventmask=EPOLLIN | EPOLLERR | EPOLLHUP)

def reset_connection(fd, connections, poll_object, requests):
	
	# Restart the given connection as long as attempts + 1 isn't equal to max_attempts
	
	connection = connections[fd]
	
	# Update request table
	for request_id in connection["request_ids"]:
		requests[request_id]["connections"].remove(fd)
	
	# Unregister connection's output and kill connection
	del connections[fd]
	poll_object.unregister(connection["process"].stdout)
	connection["process"].kill()
	
	# Open new connection if conditions are met
	if connection["attempts"] + 1 < max_connections_attempts and unfinished_requests_left(requests):
		sleep(reconnect_delay)
		open_connection(connection["host"], connection["attempts"] + 1, connections, poll_object)

def count_unfinished_requests_left(requests):
	amount = 0
	for request in requests:
		if not request["finished"]:
			amount += 1
	return amount

def unfinished_requests_left(requests):
	for request in requests:
		if not request["finished"]:
			return True
	return False

def get_unfinished_request_id(requests):
	
	# Gets an unfinished request with a minimal amount of connections currently handling it
	# Returns -1 if all requests are finished already
	min_connection_count = 1000
	min_request_id = -1
	for i in range(len(requests)):
		request = requests[i]
		if not request["finished"]:
			connection_count = len(request["connections"])
			if connection_count < min_connection_count:
				min_request_id = i
				min_connection_count = connection_count
				if connection_count == 0:
					break
	return min_request_id

def kill_request(connection, request_id):
	
	# Informs the connection that the request should be terminated
	connection["process"].stdin.write(struct.pack("I", 1))
	connection["process"].stdin.write(struct.pack("I", request_id))
	connection["process"].stdin.flush()

def find(match_string):
	
	for host in hosts:
		print("Killing all ANet processes on " + host)
		p = Popen(["ssh", "-o", "ProxyCommand ssh -q cs nc " + host + ".cs.kotnet.kuleuven.be 22", "%s@cs-"%student_id + host, "for pid in $(ps -ef | grep \"" + match_string + "\" | awk '{print $2}'); done"])
		stdout, stderr = p.communicate()
		if not stderr is None:
			print("Got stderr!")

def killall(match_string):
	
	for host in hosts:
		print("Killing all ANet processes on " + host)
		p = Popen(["ssh", "-o", "ProxyCommand ssh -q cs nc " + host + ".cs.kotnet.kuleuven.be 22", "%s@cs-"%student_id + host, "for pid in $(ps -ef | grep \"" + match_string + "\" | awk '{print $2}'); do kill -9 $pid; done"])
		stdout, stderr = p.communicate()
		if not stderr is None:
			print("Got stderr!")

def main():
	
	# Check input
	if len(sys.argv) < 2:
		print("Usage: anet <batch-file> [dependencies] | anet --find <match-string> | anet --killall <match-string>")
		return
	
	if sys.argv[1] == "--find":
		find(sys.argv[2])
		return
	
	if sys.argv[1] == "--killall":
		killall(sys.argv[2])
		return

	# Copy dependencies with rsync if necessary
	copy_dependencies = (len(sys.argv) > 2)
	if copy_dependencies:
		dependencies_rsync = Popen(["rsync", "-e", "ssh -o 'ProxyCommand ssh -q cs nc aalst.cs.kotnet.kuleuven.be 22' -l %s"%student_id, "--update", "--delete", "--archive", sys.argv[2], "cs-aalst:/home/%s/anet/dependencies"%student_id])

	# Read requests
	with open(sys.argv[1], "r") as f:
		commands = list(filter(lambda element : element != "", f.read().split("\n")))
	requests = []
	for command in commands:
		requests.append({
			"command": command,
			"finished": False,
			"connections": []
		})
	
	# Start SSH connections
	poll_object = epoll()
	connections = {} # A dictionary mapping file descriptors to [process, host, attempts, request_id]-dictionaries. Host is used to reopen connection upon failure. Attempts keeps track of how many failed attempts to connect have occurred. If attempts is -1, this indicates that the connection opened correctly.
	for host in hosts:
		
		# Open new connection
		open_connection(host, 0, connections, poll_object)
		
		# Check if we still need more connections
		if len(connections) >= len(requests):
			break

	# Wait for rsync to finish if necessary
	if copy_dependencies:
		dependencies_rsync.wait()
	
	# Handle requests until there are no open connections anymore
	# If a connection ERR's or HUP's, we ignore its output
	while unfinished_requests_left(requests):
		
		if printing:
			sys.stderr.write("Connections: %s\n"%len(connections))
			sys.stderr.write("Unfinished requests left: %s\n"%count_unfinished_requests_left(requests))
			sys.stderr.flush()
		
		# Wait for events
		events = poll_object.poll()
		
		# Handle events
		for fd, event in events:
			
			connection = connections[fd]
			if event & (EPOLLERR | EPOLLHUP):
				
				# ERR or HUP occurred
				# Restart connection
				reset_connection(fd, connections, poll_object, requests)
			
			elif event & EPOLLIN:
				
				# Received output
				
				connections_to_check = [fd] # Connections which may need new requests after event handling
				
				# If connection isn't marked as open yet, check if dispatcher has started correctly
				if connection["attempts"] > -1:
					if connection["process"].stdout.read(len(magic_string)).decode("utf-8") == magic_string:
						# Connection opened successfully, mark connection as open
						connection["attempts"] = -1
					else:
						# Connection somehow returned output which didn't match target string, abort connection
						if printing:
							sys.stderr.write("Connection somehow returned output which didn't match target string! Aborting connection.\n")
							sys.stderr.flush()
						reset_connection(fd, connections, poll_object, requests)
				
				# If connection is marked as open but non-free, return response if process exited correctly
				if connection["attempts"] == -1 and len(connection["request_ids"]) > 0:
					
					# Parse header
					raw_request_id = connection["process"].stdout.read(4)
					request_id = struct.unpack("I", raw_request_id)[0]
					raw_length = connection["process"].stdout.read(4)
					length = struct.unpack("I", raw_length)[0]
					if printing and (request_id >= len(requests) or length not in (0, 512*512*8*8//len(requests) + 16)):
						sys.stderr.write("Received bytes: " + str(raw_request_id) + "\n")
						sys.stderr.write("Received request ID: %s\n"%request_id)
						sys.stderr.write("Received length: %s vs expected length: %s\n"%(length, 512*512*8*8//len(requests) + 16))
						sys.stderr.write(str(requests) + "\n")
						sys.stderr.flush()
					request = requests[request_id]
					if length == -1:
						
						# Process crashed, don't return response
						if printing:
							sys.stderr.write("Crash from host: " + connection["host"] + "\n")
							sys.stderr.write("Intended: " + str(not(request_id in connection["request_ids"])) + "\n")
							sys.stderr.flush()
						if request_id in connection["request_ids"]:
							# Only try to remove if it hasn't been removed yet
							request["connections"].remove(fd)
							connection["request_ids"].remove(request_id)
						
					else:
						
						# Process exited correctly, read response even if request was already finished by other connection
						response = bytearray()
						while len(response) < length:
							response += connection["process"].stdout.read(length - len(response))
						if not request["finished"]:
							# Request has not yet been finished by other connections
							request["finished"] = True
							request["connections"].remove(fd)
							connection["request_ids"].remove(request_id)
							for fd in request["connections"]:
								# Inform connection to kill process
								kill_request(connections[fd], request_id)
								connections[fd]["request_ids"].remove(request_id)
								connections_to_check.append(fd)
							request["connections"] = []
							if printing:
								sys.stderr.write("Received from host: " + connection["host"] + "\n")
								sys.stderr.flush()
							# Return response
							sys.stdout.buffer.write(raw_request_id)
							sys.stdout.buffer.write(raw_length)
							sys.stdout.buffer.write(response)
							sys.stdout.flush()
				
				for check_fd in connections_to_check:
					
					check_connection = connections[check_fd]
					# While connection is marked as open and free, start new request
					while check_connection["attempts"] == -1 and len(check_connection["request_ids"]) < processes_per_host:
						
						# Add request to host
						request_id = get_unfinished_request_id(requests)
						
						if request_id != -1:
							
							check_connection["request_ids"].append(request_id)
							requests[request_id]["connections"].append(check_fd)
							command = requests[request_id]["command"]
							
							# Start new request
							check_connection["process"].stdin.write(struct.pack("I", 0))
							check_connection["process"].stdin.write(struct.pack("I", request_id))
							check_connection["process"].stdin.write(struct.pack("I", len(command)))
							check_connection["process"].stdin.write(command.encode("utf-8"))
							check_connection["process"].stdin.flush()
						
						else:
							
							# All requests have already finished
							break
	
	# Close all connections
	for fd in connections.keys():
		connection = connections[fd]
		poll_object.unregister(connection["process"].stdout)
		# Kill any requests left on this connection
		for request_id in connection["request_ids"]:
			connection["process"].stdin.write(struct.pack("I", 1))
			connection["process"].stdin.write(struct.pack("I", request_id))
			connection["process"].stdin.flush()
		connection["process"].stdin.close() # Makes dispatcher terminate
	
	# Kill all remaining connections
	for fd in connections.keys():
		connections[fd]["process"].kill()



main()
