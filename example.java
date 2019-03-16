// This code is taken from my ray-tracing project so maybe don't copy it too much unless you want to trigger the plagiarism detector. That being said, all code here is irrelevant for the actual rendering.
// You can't actually compile/execute this, this is just some example code to give an idea of how a client program could operate.



// imports here ...

public class Main {
	
	// variables here ...

	public static void main(String[] args) {
			
		// Distribute rendering using ANet
		
		// Create batch file
		jobs = Job.prepareJobs(...);
		try {
			PrintWriter writer = new PrintWriter("batch_file.txt");
			for(Job job : jobs)
				writer.println(/* write something with job */);
			writer.close();
		} catch (FileNotFoundException e) {
			e.printStackTrace();
		}
		
		// Start ANet
		try {
			this.anet = Runtime.getRuntime().exec("anet batch_file.txt");
		} catch (IOException e) {
			e.printStackTrace();
		}
		
		// Collect results when they arrive
		
		while (true) {
			
			// Read header
			int request_id = Main.readInt(this.anet.getInputStream());
			if (request_id == -1) {
				// Nothing left, leave loop
				break;
			}
			int length = Main.readInt(this.anet.getInputStream());
			
			// Read and parse response
			// read length bytes from stream
			
		}
			
	}
	
	public static int readInt(InputStream stream) {
		
		// Reads and returns a 4-byte little-endian integer from the given stream
		// Returns -1 if something went wrong (including EOF)
		
		byte[] bytes = new byte[4];
		try {
			if (stream.read(bytes) == -1) {
				return -1;
			} else {
				// Bytes were read successfully, parse and return value
				int value = 0;
				for(int i = 0; i < 4; i++)
					value += (bytes[i] & 0xFF) << (8*i);
				return value;
			}
		} catch (IOException e) {
			e.printStackTrace();
			return -1;
		}
		
	}
	
}
