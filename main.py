from flask import Flask, jsonify
import subprocess
import os
import signal
from datetime import datetime
import time

app = Flask(__name__)
recording_process = None

@app.route('/status', methods=['GET'])
def check_status():
    # Check if iOS Simulator is running
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to count processes whose name is "Simulator"'],
        capture_output=True, text=True
    )
    
    simulator_running = int(result.stdout.strip()) > 0
    
    # Check if we have an active recording process
    global recording_process
    recording_active = recording_process is not None and recording_process.poll() is None
    
    return jsonify({
        "simulator_running": simulator_running,
        "recording_active": recording_active
    })

@app.route('/start', methods=['GET'])
def start_recording():
    global recording_process
    
    # Check if Simulator is running
    sim_check = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to count processes whose name is "Simulator"'],
        capture_output=True, text=True
    )
    
    simulator_running = int(sim_check.stdout.strip()) > 0
    
    if not simulator_running:
        # Automatically open iOS Simulator if not running
        subprocess.call([
            "osascript", "-e",
            '''
            tell application "Simulator"
                activate
            end tell
            '''
        ])
        # Wait for Simulator to start
        time.sleep(5)
        # Verify simulator is now running
        sim_check = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to count processes whose name is "Simulator"'],
            capture_output=True, text=True
        )
        simulator_running = int(sim_check.stdout.strip()) > 0
        if not simulator_running:
            return jsonify({"error": "Failed to start iOS Simulator"}), 500
    
    # Check if already recording
    if recording_process is not None and recording_process.poll() is None:
        return jsonify({"error": "Recording already in progress"}), 400
    
    try:
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Set output path in project folder
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"meow_app_{timestamp}.mov")
        
        # Start recording using xcrun simctl
        recording_process = subprocess.Popen(
            ["xcrun", "simctl", "io", "booted", "recordVideo", output_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # To make it a process group leader so we can kill it later
        )
        
        # Wait a moment to confirm recording started
        time.sleep(1)
        
        # Check if process started successfully
        if recording_process.poll() is not None:
            return jsonify({"error": "Failed to start recording process"}), 500
            
        return jsonify({
            "status": "Simulator recording started",
            "file_path": output_path
        })
    except Exception as e:
        return jsonify({"error": f"Failed to start Simulator recording: {e}"}), 500

@app.route('/stop', methods=['GET'])
def stop_recording():
    global recording_process
    
    if recording_process is None or recording_process.poll() is not None:
        return jsonify({"error": "No active recording to stop"}), 400
    
    try:
        # Get file path before stopping
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"meow_app_{timestamp}.mov")
        
        # Send SIGINT (Ctrl+C) to the recording process
        os.killpg(os.getpgid(recording_process.pid), signal.SIGINT)
        
        # Wait for process to terminate
        timeout = 5
        start_time = time.time()
        while recording_process.poll() is None and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        # If process didn't terminate, force kill it
        if recording_process.poll() is None:
            os.killpg(os.getpgid(recording_process.pid), signal.SIGKILL)
            recording_process.wait()
        
        recording_process = None
        
        # Give a moment for the file to be properly saved
        time.sleep(1)
        
        return jsonify({
            "status": "Recording stopped and saved"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to stop recording: {e}"}), 500

@app.route('/pause', methods=['GET'])
def pause_recording():
    # xcrun simctl recordVideo doesn't support pausing
    return jsonify({"error": "Pausing is not supported with simctl recordVideo"}), 400
        
@app.route('/resume', methods=['GET'])
def resume_recording():
    # xcrun simctl recordVideo doesn't support resuming
    return jsonify({"error": "Resuming is not supported with simctl recordVideo"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)