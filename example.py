# Example client program to do some very useful work

import subprocess
import struct

# Create batch file
batch = ""
job_size = 1000000
jobs = 1000
for i in range(0, jobs):
	batch = batch + "python3 dependencies/example_worker.py %s %s\n"%(i*job_size, (i + 1)*job_size)
with open("batch_file.txt", "w") as f:
	f.write(batch[:-1])

# Start batch and parse responses
finished = [False]*jobs
process = subprocess.Popen(["anet", "batch_file.txt", "example_worker.py"], stdout=subprocess.PIPE)
while False in finished:
	request_id = struct.unpack("I", process.stdout.read(4))[0]
	length = struct.unpack("I", process.stdout.read(4))[0]
	response = process.stdout.read(length).decode()
	finished[request_id] = True
	print("Finished request %s, finished %s/%s requests"%(request_id, finished.count(True), jobs))
	if length > 0:
		print("\nFOUND SOLUTION: %s\n"%response)
