import os
import sys
import ftplib

def get_env_var(name):
    return os.environ.get(name, "").strip()

def connect_ftp(host, user, passwd):
    print(f"--- Attempting connection to host: '{host}' ---")
    
    # 1. Try FTPS (Explicit TLS over port 21)
    print(f"1. Trying FTPS (Explicit TLS) on {host}:21...")
    try:
        ftps = ftplib.FTP_TLS()
        ftps.connect(host, 21, timeout=20)
        ftps.login(user, passwd)
        ftps.prot_p()  # Encrypt data channel
        ftps.set_pasv(True)
        print(f"SUCCESS: Connected to {host} via FTPS!")
        return ftps
    except Exception as e:
        print(f"FTPS connection to {host} failed: {e}")

    # 2. Try Standard FTP (Plain text over port 21)
    print(f"2. Trying Plain FTP on {host}:21...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, 21, timeout=20)
        ftp.login(user, passwd)
        ftp.set_pasv(True)
        print(f"SUCCESS: Connected to {host} via Plain FTP!")
        return ftp
    except Exception as e:
        print(f"Plain FTP connection to {host} failed: {e}")
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
                print(f"Creating remote directory: {current}")
                ftp.mkd(current)
                ftp.cwd(current)
            except Exception as e:
                print(f"Warning: Could not create/cd directory {current}: {e}")

def upload_dir(ftp, local_dir, remote_dir):
    ensure_remote_dir(ftp, remote_dir)
    target_base = "/" + remote_dir.strip("/")

    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        if rel_path == ".":
            current_remote = target_base
        else:
            current_remote = target_base + "/" + rel_path.replace("\\", "/")
        
        ensure_remote_dir(ftp, current_remote)

        for f in files:
            local_file_path = os.path.join(root, f)
            print(f"Uploading: {rel_path}/{f} -> {current_remote}/{f}")
            with open(local_file_path, "rb") as fp:
                ftp.storbinary(f"STOR {f}", fp)

def main():
    raw_server = get_env_var("FTP_SERVER").replace("https://", "").replace("http://", "").replace("ftp://", "").strip("/")
    user = get_env_var("FTP_USERNAME")
    passwd = get_env_var("FTP_PASSWORD")
    remote_dir = get_env_var("FTP_REMOTE_DIR") or "/very-good.biz/public_html/event.very-good.biz"
    local_dir = "./dist"

    if not raw_server or not user or not passwd:
        print("Error: Missing FTP_SERVER, FTP_USERNAME, or FTP_PASSWORD environment variables.")
        sys.exit(1)

    hosts_to_try = [raw_server]
    # Fallback host for StarServer
    star_server_host = "ss462060.stars.ne.jp"
    if star_server_host not in hosts_to_try:
        hosts_to_try.append(star_server_host)

    ftp = None
    for host in hosts_to_try:
        ftp = connect_ftp(host, user, passwd)
        if ftp:
            break

    if not ftp:
        print("\n[ERROR] Could not connect to FTP server using any host or protocol.")
        print("Possible causes:")
        print("1. StarServer FTP_SERVER secret value is incorrect.")
        print("2. StarServer is blocking connections from GitHub Actions IP range (Overseas IP block).")
        sys.exit(1)

    try:
        print(f"\nStarting file upload from '{local_dir}' to '{remote_dir}'...")
        upload_dir(ftp, local_dir, remote_dir)
        ftp.quit()
        print("\n[SUCCESS] FTP deployment finished successfully!")
    except Exception as e:
        print(f"\n[ERROR] Deployment failed during upload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
