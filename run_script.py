import subprocess
import os

# Activate the virtual environment
# Note: You need to use 'call' for Windows batch commands
activate_venv = r"venv\Scripts\activate"
subprocess.call(activate_venv, shell=True)

# Start the Uvicorn server
uvicorn_command = "uvicorn app.main:app --reload"
subprocess.Popen(uvicorn_command, shell=True)

# Start the Steamlit server
steamlit_command = "python -m streamlit run app/chatbot_ui.py"
subprocess.Popen(steamlit_command, shell=True)

print("Uvicorn server is running...")
