import shutil
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FOLDER = os.path.join(BASE_DIR, "..", "databases")
BACKUP_FOLDER = os.path.join(BASE_DIR, "..", "backups")

def create_backup():
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}")
    
    if os.path.exists(DB_FOLDER):
        shutil.copytree(DB_FOLDER, backup_path)
        print(f"Backup created at: {backup_path}")
        
        # Keep only last 5 backups
        backups = sorted([os.path.join(BACKUP_FOLDER, d) for d in os.listdir(BACKUP_FOLDER)], key=os.path.getmtime)
        while len(backups) > 5:
            old_backup = backups.pop(0)
            shutil.rmtree(old_backup)
            print(f"Removed old backup: {old_backup}")
    else:
        print("Source database folder not found.")

if __name__ == "__main__":
    create_backup()
