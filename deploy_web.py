import os
import sys
import zipfile
import io
import urllib.request
import urllib.parse
import json

def get_env_var(name):
    return os.environ.get(name, "").strip()

def main():
    deploy_url = get_env_var("WEB_DEPLOY_URL") or "https://event.very-good.biz/deploy.php"
    deploy_secret = get_env_var("WEB_DEPLOY_SECRET") or "ShizuokaEventNavi2026SecretKey"
    dist_dir = "./dist"

    print(f"Starting HTTPS Web Deployment to: {deploy_url}")

    if not os.path.exists(dist_dir):
        print(f"[ERROR] Directory '{dist_dir}' does not exist.")
        sys.exit(1)

    # 1. Compress dist directory into in-memory zip
    print(f"Compressing static site files in '{dist_dir}'...")
    zip_buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, dist_dir)
                zf.write(abs_path, rel_path)
                file_count += 1

    zip_bytes = zip_buffer.getvalue()
    print(f"Compressed {file_count} files into zip archive ({len(zip_bytes)} bytes).")

    # 2. Build multipart/form-data POST request
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    
    # Add file parameter
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="file"; filename="dist.zip"'.encode("utf-8"))
    body.append(b"Content-Type: application/zip\r\n")
    body.append(zip_bytes)
    
    # End boundary
    body.append(f"--{boundary}--".encode("utf-8"))
    body.append(b"")

    payload = b"\r\n".join(body)

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload)),
        "X-Deploy-Token": deploy_secret,
        "User-Agent": "GitHub-Actions-WebDeploy/1.0"
    }

    # 3. Send HTTPS POST request
    print(f"Sending HTTPS deployment request to {deploy_url}...")
    req = urllib.request.Request(deploy_url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_body = response.read().decode("utf-8")
            status = response.status
            print(f"Server Response ({status}):\n{res_body}")

            if status == 200 and "SUCCESS" in res_body:
                print("\n[SUCCESS] Web deployment completed successfully in < 2 seconds!")
            else:
                print(f"\n[ERROR] Deployment failed with server response: {res_body}")
                sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] HTTPS deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
