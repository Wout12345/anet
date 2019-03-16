"""
A simple program which forwards commands from stdin and their output and error streams to stdout and stderr.
When the program starts, a magic string is sent to stdout.
Commands should be followed by a newline.
When a child process finishes with return code zero, we first print the length of its response in bytes as a 4-byte-integer (responses can never be longer than 4GB since each machine only allocates 2GB memory to SSH users) followed by its response.
When a child process exits with a non-zero return code, we only return -1 as its length, with no response, to indicate a crash.
stderr is forwarded without further interference
"""

import sys
from os import fdopen
import struct
from subprocess import Popen, PIPE, call
from select import epoll, EPOLLIN, EPOLLERR, EPOLLHUP

# Set-up
student_id = "r0597343"
printing = False
magic_string = "anet_dispatcher started successfully."
sys.stdout.write(magic_string)
sys.stdout.flush()
processes = {} # A dictionary mapping process.stdout.name to [process, request_id]-dictionaries
unbuffered_stdin = fdopen(sys.stdin.fileno(), "rb", 0) # We create a separate reader which doesn't buffer, so epoll always knows if there is actually data left to be read
poll_object = epoll()
poll_object.register(unbuffered_stdin, eventmask=EPOLLIN | EPOLLERR | EPOLLHUP)
should_run = True

while should_run:
	
	# Wait for events
	events = poll_object.poll()
	
	# Handle events
	for fd, event in events:
		
		if fd == unbuffered_stdin.fileno():
			
			# Event comes from standard input stream
			
			if event & (EPOLLERR | EPOLLHUP):
				
				# Connection ended, kill dispatcher
				should_run = False
				break
				
			elif event & EPOLLIN:
				
				# Received new message
				message_type = struct.unpack("I", unbuffered_stdin.read(4))[0]
				request_id = struct.unpack("I", unbuffered_stdin.read(4))[0]
				if message_type == 0:
					# Start new process
					command_length = struct.unpack("I", unbuffered_stdin.read(4))[0]
					command = unbuffered_stdin.read(command_length).decode("utf-8")
					p = Popen("cd /home/%s/anet/ ; exec %s"%(student_id, command), bufsize=0, shell=True, stdout=PIPE) # exec is necessary to not spawn a separate shell, allows us to kill actual process
					processes[p.stdout.fileno()] = {
						"process": p,
						"request_id": request_id
					}
					poll_object.register(p.stdout, eventmask=EPOLLIN | EPOLLERR | EPOLLHUP)
				elif message_type == 1:
					# Kill process
					p = None
					for process in processes.values():
						if process["request_id"] == request_id:
							p = process["process"]
							break
					if not (p is None):
						# Process is still there
						poll_object.unregister(p.stdout)
						del processes[p.stdout.fileno()]
						p.kill()
						p.communicate()
		
		elif fd in processes.keys():
			
			# Event comes from one of child processes
			# Child process either has ended or will end soon, so we remove it right away (before file descriptor closes)
			
			process = processes[fd]
			poll_object.unregister(process["process"].stdout)
			del processes[process["process"].stdout.fileno()]
			sys.stdout.buffer.write(struct.pack("I", process["request_id"])) # Return request_id
	
			if printing:
				sys.stderr.write("Wrote request ID: " + str(struct.pack("I", process["request_id"])) + "\n")
				sys.stderr.flush()
			
			if event & EPOLLERR:
				
				# Crash occurred
				sys.stdout.buffer.write(struct.pack("I", -1)) # Return 0
			
			elif event & (EPOLLIN | EPOLLHUP):
				
				# Program finished (or in the case of EPOLLIN, will finish soon but we can't wait for EPOLLHUP since the OS buffer may fill up and block the child process)
				response = process["process"].stdout.read()
				process["process"].communicate()
				if process["process"].returncode != 0:
					# Crash occurred
					sys.stdout.buffer.write(struct.pack("I", -1)) # Return 0
				else:
					# Program finished successfully
					sys.stdout.buffer.write(struct.pack("I", len(response))) # Response length
					sys.stdout.flush()
					sys.stdout.buffer.write(response) # Response
			
					if printing:
						sys.stderr.write("Wrote length: " + str(len(response)) + "\n")
						sys.stderr.flush()
			
			sys.stdout.flush()

# Kill any remaining child processes
for process in processes.values():
	poll_object.unregister(process["process"].stdout)
	process["process"].kill()
