import os
import sys
import socket
import traceback
import ftplib

# Set global socket timeout to 15 seconds so NO socket (control or passive data socket) ever hangs!
socket.setdefaulttimeout(15)

def log(msg):
    print(msg, flush=True)

def get_env_var(name):
    return os.environ.get(name, "").strip()

def connect_ftp(host, user, passwd):
    log(f"\n--- Testing host: '{host}' ---")
    try:
        ip = socket.gethostbyname(host)
        log(f"Resolved {host} -> {ip}")
    except Exception as e:
        log(f"DNS resolution failed for {host}: {e}")
        return None
    
    # 1. Try FTPS (Explicit TLS over port 21)
    log(f"1. Attempting FTPS (Explicit TLS) to {host}:21 (timeout=15s)...")
    try:
        ftps = ftplib.FTP_TLS()
        ftps.connect(host, 21, timeout=15)
        ftps.login(user, passwd)
        ftps.prot_p()  # Encrypt data channel
        ftps.set_pasv(True)
        log(f"SUCCESS: Connected to {host} via FTPS!")
        return ftps
    except Exception as e:
        log(f"FTPS failed for {host}: {e}")

    # 2. Try Standard FTP (Plain text over port 21)
    log(f"2. Attempting Plain FTP to {host}:21 (timeout=15s)...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, 21, timeout=15)
        ftp.login(user, passwd)
        ftp.set_pasv(True)
        log(f"SUCCESS: Connected to {host} via Plain FTP!")
        return ftp
    except Exception as e:
        log(f"Plain FTP failed for {host}: {e}")
        return None

def ensure_remote_dir(ftp, remote_dir):
    parts = [p for p in remote_dir.strip("/").split("/") if p]
    current = ""
    for part in parts:
        current += "/" + part
        try:
            ftp.cwd(current)
        except ftplib.error_perm:
            try:
                log(f"Creating directory: {current}")
                ftp.mkd(current)
                ftp.cwd(current)
            except Exception as e:
                log(f"Warning: Could not create/cd {current}: {e}")

def upload_dir(ftp, local_dir, remote_dir):
    ensure_remote_dir(ftp, remote_dir)
    target_base = "/" + remote_dir.strip("/")

    file_count = 0
    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        if rel_path == ".":
            current_remote = target_base
        else:
            current_remote = target_base + "/" + rel_path.replace("\\", "/")
        
        ensure_remote_dir(ftp, current_remote)

        for f in files:
            local_file_path = os.path.join(root, f)
            log(f"Uploading [{file_count+1}]: {rel_path}/{f} -> {current_remote}/{f}")
            with open(local_file_path, "rb") as fp:
                ftp.storbinary(f"STOR {f}", fp)
            file_count += 1
    log(f"Uploaded total {file_count} files.")

def main():
    raw_server = get_env_var("FTP_SERVER").replace("https://", "").replace("http://", "").replace("ftp://", "").strip("/")
    user = get_env_var("FTP_USERNAME")
    passwd = get_env_var("FTP_PASSWORD")
    remote_dir = get_env_var("FTP_REMOTE_DIR") or "/very-good.biz/public_html/event.very-good.biz"
    local_dir = "./dist"

    log(f"Starting FTP deployment to remote_dir: {remote_dir}")
    log(f"Configured FTP_SERVER secret: '{raw_server}'")
    log(f"Configured FTP_USERNAME secret: '{user}'")

    if not raw_server or not user or not passwd:
        log("[ERROR] Missing required secrets: FTP_SERVER, FTP_USERNAME, or FTP_PASSWORD.")
        sys.exit(1)

    hosts_to_try = []
    if raw_server:
        hosts_to_try.append(raw_server)
    
    # Common StarServer FTP host patterns
    star_server_host = "ss462060.stars.ne.jp"
    if star_server_host not in hosts_to_try:
        hosts_to_try.append(star_server_host)

    ftp = None
    for host in hosts_to_try:
        ftp = connect_ftp(host, user, passwd)
        if ftp:
            break

    if not ftp:
        log("\n[ERROR] All FTP/FTPS connection attempts timed out or failed.")
        sys.exit(1)

    try:
        log(f"\nStarting file upload from '{local_dir}'...")
        upload_dir(ftp, local_dir, remote_dir)
        ftp.quit()
        log("\n[SUCCESS] Deployment completed successfully!")
    except Exception as e:
        log(f"\n[ERROR] Failed during upload: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
