from flask import Flask, jsonify
import subprocess
import os
from datetime import datetime

app = Flask(__name__)
quicktime_process = None

@app.route('/status', methods=['GET'])
def check_status():
    # Check if QuickTime Player is running
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
        capture_output=True, text=True
    )
    
    quicktime_running = int(result.stdout.strip()) > 0
    
    # Check if we have an active recording process
    recording_active = quicktime_process is not None
    
    return jsonify({
        "quicktime_running": quicktime_running,
        "recording_active": recording_active
    })

@app.route('/start', methods=['GET'])
def start_recording():
    global quicktime_process
    
    # Check if QuickTime is already running
    qt_check = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
        capture_output=True, text=True
    )
    
    quicktime_already_running = int(qt_check.stdout.strip()) > 0
    
    # Đóng QuickTime cũ nếu có
    if quicktime_process is not None:
        try:
            quicktime_process.terminate()
        except:
            pass
    
    # Mở QuickTime và bắt đầu ghi
    try:
        quicktime_process = subprocess.Popen([
            "osascript", "-e",
            '''
            tell application "QuickTime Player"
                activate
                set newScreenRecording to new screen recording
                delay 1
                tell application "System Events"
                    keystroke return
                end tell
            end tell
            '''
        ])
        
        # Wait a moment to confirm recording started
        import time
        time.sleep(2)
        
        # Check if QuickTime is now running
        qt_check_after = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
            capture_output=True, text=True
        )
        
        quicktime_running = int(qt_check_after.stdout.strip()) > 0
        
        if not quicktime_running:
            return jsonify({"error": "Failed to start QuickTime Player"}), 500
            
        return jsonify({
            "status": "QuickTime recording started",
            "previously_running": quicktime_already_running
        })
    except Exception as e:
        return jsonify({"error": f"Failed to start QuickTime: {e}"}), 500

@app.route('/stop', methods=['GET'])
def stop_recording():
    global quicktime_process
    
    try:
        # Check if QuickTime is actually running
        qt_check = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
            capture_output=True, text=True
        )
        
        if int(qt_check.stdout.strip()) == 0:
            return jsonify({"error": "QuickTime Player is not running"}), 400
        
        # Tạo tên file với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"screen_recording_{timestamp}.mov")
        
        # Kiểm tra quyền ghi thư mục
        if not os.access(os.path.dirname(save_path), os.W_OK):
            return jsonify({"error": "No write permission in directory"}), 500
        
        # Dừng và lưu QuickTime recording
        if quicktime_process is not None:
            # Tạo thư mục lưu và tên file
            save_folder = os.path.dirname(os.path.abspath(__file__))
            # Loại bỏ dấu / ở đầu nếu có
            if save_folder.startswith('/'):
                save_folder = save_folder[1:]
            file_name = f"screen_recording_{timestamp}"
            
            # Tạm thời lấy tên file QuickTime mặc định để xóa sau này
            current_date = datetime.now().strftime('%Y-%m-%d')
            home_folder = os.path.expanduser("~")
            
            # Kiểm tra và xóa file tạm thời theo định dạng "Screen Recording YYYY-MM-DD.mov"
            default_recording_name = f"Screen Recording {current_date}.mov"
            default_recording_path = os.path.join(home_folder, default_recording_name)
            
            # Kiểm tra và xóa file tạm thời theo định dạng "Screen Recording YYYY-MM-DD at HH.MM.SS.mov"
            desktop_folder = os.path.join(home_folder, "Desktop")
            
            subprocess.call([
                "osascript", "-e",
                f'''
                tell application "QuickTime Player"
                    activate
                    delay 1
                    -- Dừng ghi bằng phím tắt Command + Control + Esc
                    tell application "System Events"
                        key code 53 using {{command down, control down}}
                        delay 2
                        -- Mở hộp thoại lưu
                        keystroke "s" using command down
                        delay 1
                        -- Nhấn / để điều hướng đến đường dẫn cụ thể
                        keystroke "/"
                        delay 1
                        -- Nhập đường dẫn thư mục (không có dấu / ở đầu)
                        keystroke "{save_folder}"
                        delay 1
                        keystroke return
                        delay 1
                        -- Nhập tên file
                        keystroke "{file_name}"
                        delay 1
                        keystroke return
                    end tell
                end tell
                '''
            ])
            
            # Đợi một chút để đảm bảo file đã được lưu
            import time
            time.sleep(2)
            
            # Xóa file tạm thời ở Home nếu tồn tại
            if os.path.exists(default_recording_path):
                try:
                    os.remove(default_recording_path)
                    print(f"Đã xóa file tạm: {default_recording_path}")
                except Exception as e:
                    print(f"Không thể xóa file tạm: {e}")
            
            # Xóa file tạm thời ở Desktop với định dạng "Screen Recording YYYY-MM-DD at HH.MM.SS.mov"
            import glob
            pattern = os.path.join(desktop_folder, f"Screen Recording {current_date} at *.mov")
            temp_files = glob.glob(pattern)
            
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    print(f"Đã xóa file tạm: {temp_file}")
                except Exception as e:
                    print(f"Không thể xóa file tạm: {temp_file}, lỗi: {e}")
            
            quicktime_process.terminate()
            quicktime_process = None
        
        return jsonify({"status": "Recording stopped", "file_path": save_path})
    except Exception as e:
        return jsonify({"error": f"Failed to stop recording: {e}"}), 500

@app.route('/pause', methods=['GET'])
def pause_recording():
    try:
        # Check if QuickTime is running
        qt_check = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
            capture_output=True, text=True
        )
        
        if int(qt_check.stdout.strip()) == 0:
            return jsonify({"error": "QuickTime Player is not running"}), 400
            
        # Send space key to pause recording
        subprocess.call([
            "osascript", "-e",
            '''
            tell application "QuickTime Player"
                activate
                tell application "System Events"
                    keystroke space
                end tell
            end tell
            '''
        ])
        
        return jsonify({"status": "Recording paused"})
    except Exception as e:
        return jsonify({"error": f"Failed to pause recording: {e}"}), 500
        
@app.route('/resume', methods=['GET'])
def resume_recording():
    try:
        # Check if QuickTime is running
        qt_check = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to count processes whose name is "QuickTime Player"'],
            capture_output=True, text=True
        )
        
        if int(qt_check.stdout.strip()) == 0:
            return jsonify({"error": "QuickTime Player is not running"}), 400
            
        # Send space key to resume recording
        subprocess.call([
            "osascript", "-e",
            '''
            tell application "QuickTime Player"
                activate
                tell application "System Events"
                    keystroke space
                end tell
            end tell
            '''
        ])
        
        return jsonify({"status": "Recording resumed"})
    except Exception as e:
        return jsonify({"error": f"Failed to resume recording: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)