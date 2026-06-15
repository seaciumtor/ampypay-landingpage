<?php
// Proxy POST /api/demo.php → Python server on localhost:3001
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

$body = file_get_contents('php://input');

$ctx = stream_context_create([
    'http' => [
        'method'  => 'POST',
        'header'  => "Content-Type: application/json\r\nContent-Length: " . strlen($body) . "\r\n",
        'content' => $body,
        'timeout' => 10,
        'ignore_errors' => true,
    ]
]);

$response = file_get_contents('http://127.0.0.1:3001/api/demo', false, $ctx);

if ($response === false) {
    http_response_code(502);
    echo json_encode(['error' => 'Backend unavailable. Please try again.']);
    exit;
}

// Forward status code from Python server
$status = 200;
foreach ($http_response_header as $h) {
    if (preg_match('/^HTTP\/\S+\s+(\d+)/', $h, $m)) {
        $status = (int)$m[1];
    }
}
http_response_code($status);
echo $response;
