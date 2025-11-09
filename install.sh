
echo "Installing QueueCTL..."


python3 -m venv venv
source venv/bin/activate 


pip install -e .

echo "Installation complete!"
echo "Run: queuectl --help"