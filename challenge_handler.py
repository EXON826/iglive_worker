"""
Web endpoint to handle Instagram challenge verification on Railway.
Temporary solution to enter verification codes.
"""

from flask import Flask, request, jsonify
import threading
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variable to store the verification code
verification_code = None
code_submitted = threading.Event()


@app.route('/submit_code', methods=['POST', 'GET'])
def submit_code():
    """
    Endpoint to submit Instagram verification code.
    
    Usage:
    POST/GET to: http://your-railway-url/submit_code?code=123456
    """
    global verification_code
    
    if request.method == 'POST':
        code = request.json.get('code') or request.form.get('code')
    else:  # GET
        code = request.args.get('code')
    
    if code:
        verification_code = code
        code_submitted.set()
        logger.info(f"Verification code received: {code}")
        return jsonify({
            'success': True, 
            'message': f'Code {code} submitted successfully. Check Railway logs.'
        })
    else:
        return jsonify({
            'success': False, 
            'message': 'No code provided. Use ?code=123456'
        }), 400


@app.route('/status', methods=['GET'])
def status():
    """Check if code has been submitted"""
    return jsonify({
        'code_submitted': code_submitted.is_set(),
        'code': verification_code if code_submitted.is_set() else None
    })


@app.route('/', methods=['GET'])
def home():
    """Simple form to submit code"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Instagram Verification</title>
        <style>
            body { font-family: Arial; max-width: 500px; margin: 50px auto; padding: 20px; }
            input { padding: 10px; font-size: 16px; width: 200px; }
            button { padding: 10px 20px; font-size: 16px; background: #0095f6; color: white; border: none; cursor: pointer; }
            button:hover { background: #007ac2; }
        </style>
    </head>
    <body>
        <h1>Instagram Verification Code</h1>
        <p>Enter the 6-digit code from your email:</p>
        <form action="/submit_code" method="GET">
            <input type="text" name="code" placeholder="123456" maxlength="6" pattern="[0-9]{6}" required>
            <button type="submit">Submit</button>
        </form>
        <p style="color: #666; font-size: 12px;">Or use: /submit_code?code=123456</p>
    </body>
    </html>
    '''


def wait_for_code(timeout=300):
    """
    Wait for verification code to be submitted.
    
    Args:
        timeout: Max seconds to wait (default: 5 minutes)
        
    Returns:
        str: The verification code, or None if timeout
    """
    global verification_code, code_submitted
    
    logger.info("Waiting for verification code...")
    logger.info("Visit your Railway URL to submit the code")
    
    if code_submitted.wait(timeout=timeout):
        code = verification_code
        # Reset for next time
        verification_code = None
        code_submitted.clear()
        return code
    else:
        logger.error("Timeout waiting for verification code")
        return None


def start_challenge_server(port=8080):
    """Start the Flask server in a background thread"""
    thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False))
    thread.daemon = True
    thread.start()
    logger.info(f"Challenge handler server started on port {port}")
