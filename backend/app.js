const http = require('http');
const url = require('url'); // Import the URL module

const hostname = '0.0.0.0';
const port = 3000;

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true); // Parse the URL to get the pathname

  console.log(`[${new Date().toISOString()}] Received request: ${req.method} ${req.url}`);
  console.log('Headers:', req.headers);

  let body = '';
  req.on('data', chunk => {
    body += chunk.toString();
  });

  req.on('end', () => {
    console.log('Body:', body);

    // --- Add basic routing logic ---
    if (parsedUrl.pathname === '/') {
      // Handle requests to the root path
      res.statusCode = 200;
      res.setHeader('Content-Type', 'text/plain');
      res.end(`Hello from Node.js (via proxy)!\\nMethod: ${req.method}\\nURL: ${req.url}\\nHeaders: ${JSON.stringify(req.headers, null, 2)}\\nBody: ${body}\\n`);
    } else {
      // Handle all other paths (i.e., non-existent paths)
      res.statusCode = 404;
      res.setHeader('Content-Type', 'text/plain');
      res.end(`Page Not Found (via proxy)!\\nMethod: ${req.method}\\nURL: ${req.url}\\nHeaders: ${JSON.stringify(req.headers, null, 2)}\\n`);
    }
  });
});

server.listen(port, hostname, () => {
  console.log(`Node.js server running at http://${hostname}:${port}/`);
});
