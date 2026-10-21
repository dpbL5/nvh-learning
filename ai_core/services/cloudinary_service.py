import os
import hashlib
import time
import ipaddress
import socket
import re
from urllib.parse import urlparse, unquote

import requests

CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', 'dvwkjiz2i')


def _credentials():
    api_key = (os.getenv('CLOUDINARY_API_KEY') or '').strip()
    api_secret = (os.getenv('CLOUDINARY_API_SECRET') or '').strip()
    if not api_key or not api_secret:
        return None, None
    return api_key, api_secret


def get_upload_signature():
    """Return signed-upload parameters for browser uploads, or None if unconfigured."""
    api_key, api_secret = _credentials()
    if not api_key:
        return None
    timestamp = int(time.time())
    to_sign = f"timestamp={timestamp}"
    signature = hashlib.sha1(f"{to_sign}{api_secret}".encode('utf-8')).hexdigest()
    return {
        'cloud_name': CLOUDINARY_CLOUD_NAME,
        'api_key': api_key,
        'timestamp': timestamp,
        'signature': signature,
    }


def is_allowed_remote_url(url):
    """Allow server-side downloads only from public Cloudinary hosts."""
    try:
        parsed = urlparse(str(url))
        if parsed.scheme != 'https':
            return False
        host = (parsed.hostname or '').lower()
        if not host:
            return False
        if host != 'cloudinary.com' and not host.endswith('.cloudinary.com'):
            return False
        for result in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(result[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


def cloudinary_asset_from_url(url):
    """Derive (public_id, resource_type) from a Cloudinary delivery URL."""
    try:
        parsed = urlparse(str(url))
        parts = [part for part in parsed.path.split('/') if part]
        if 'upload' not in parts:
            return None, None
        index = parts.index('upload')
        if index == 0:
            return None, None
        resource_type = parts[index - 1]
        remainder = parts[index + 1:]
        if remainder and re.fullmatch(r'v\d+', remainder[0]):
            remainder = remainder[1:]
        public_id = unquote('/'.join(remainder))
        if not public_id:
            return None, None
        if resource_type == 'image':
            public_id = os.path.splitext(public_id)[0]
        return public_id, resource_type
    except Exception:
        return None, None


def upload_to_cloudinary(file_bytes_or_path, file_name=None, resource_type='auto'):
    files = {}
    if isinstance(file_bytes_or_path, str) and os.path.exists(file_bytes_or_path):
        files['file'] = open(file_bytes_or_path, 'rb')
    elif isinstance(file_bytes_or_path, bytes):
        files['file'] = (file_name or 'upload.png', file_bytes_or_path)
    else:
        raise ValueError("Invalid file data")

    signature_data = get_upload_signature()
    if not signature_data:
        if 'file' in files and hasattr(files['file'], 'close'):
            files['file'].close()
        print("Cloudinary API key/secret missing. Upload skipped.")
        return None

    data = {
        'api_key': signature_data['api_key'],
        'timestamp': signature_data['timestamp'],
        'signature': signature_data['signature'],
    }

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/{resource_type}/upload"

    try:
        resp = requests.post(url, data=data, files=files, timeout=60)
        resp.raise_for_status()
        res_json = resp.json()
        return {
            'secure_url': res_json.get('secure_url'),
            'public_id': res_json.get('public_id'),
        }
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None
    finally:
        if isinstance(file_bytes_or_path, str) and 'file' in files:
            files['file'].close()


def delete_from_cloudinary(public_id, resource_type='image'):
    """Delete a Cloudinary asset by public_id."""
    api_key, api_secret = _credentials()
    if not api_key:
        print("Cloudinary API key/secret missing. Skipping deletion.")
        return False

    timestamp = int(time.time())
    params_to_sign = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(params_to_sign.encode('utf-8')).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/{resource_type}/destroy"
    payload = {
        'public_id': public_id,
        'timestamp': timestamp,
        'api_key': api_key,
        'signature': signature,
    }

    try:
        resp = requests.post(url, data=payload, timeout=30)
        resp.raise_for_status()
        res_json = resp.json()
        print(f"Cloudinary destroy result for {public_id}: {res_json.get('result')}")
        return res_json.get('result') == 'ok'
    except Exception as e:
        print(f"Cloudinary deletion failed for {public_id}: {e}")
        return False
