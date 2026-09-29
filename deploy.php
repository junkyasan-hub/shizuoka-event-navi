<?php
/**
 * Shizuoka Event Navi - Secure Web Deployment Script
 * Place this file inside: /very-good.biz/public_html/event.very-good.biz/deploy.php
 */

// Set your secret key here (must match WEB_DEPLOY_SECRET in GitHub Secrets)
$SECRET_KEY = 'ShizuokaEventNavi2026SecretKey';

header('Content-Type: text/plain; charset=utf-8');

// 1. Verify Secret Token
$token = $_SERVER['HTTP_X_DEPLOY_TOKEN'] ?? $_POST['token'] ?? '';
if (empty($SECRET_KEY) || $token !== $SECRET_KEY) {
    http_response_code(403);
    die("Error 403: Forbidden - Invalid deployment token.\n");
}

// 2. Ensure POST Request
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die("Error 405: Method Not Allowed\n");
}

// 3. Receive Uploaded Zip File
if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    die("Error 400: No file received or upload failed.\n");
}

$tmp_file = $_FILES['file']['tmp_name'];
$zip = new ZipArchive();

if ($zip->open($tmp_file) === TRUE) {
    $target_dir = __DIR__;
    $zip->extractTo($target_dir);
    $zip->close();
    echo "SUCCESS: Extracted updated site files to " . $target_dir . "\n";
} else {
    http_response_code(500);
    echo "Error 500: Failed to extract uploaded zip archive.\n";
}
