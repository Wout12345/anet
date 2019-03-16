# Example worker to do some complex calculations given a certain input

import sys
import hashlib

for i in range(int(sys.argv[1]), int(sys.argv[2])):
	if hashlib.sha512(str(i).encode()).hexdigest() == "aee4ef339200ecfbe02db2215c34a04d229948fef20676272d99a6dd82785f0f1997ad8aedfd5282508f7248b4b815719d3441bad8b34b8610a64d273ed9346a":
		print(i)
		break
