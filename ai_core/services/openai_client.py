import os
import json
import base64
from typing import Any, Dict, List, Optional, Union

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

API_KEY = os.getenv('OPENAI_API_KEY', '')
DEFAULT_MODEL = os.getenv('OPENAI_MODEL_NAME', 'gpt-4o-mini')
EMBED_MODEL = os.getenv('OPENAI_EMBED_MODEL', 'text-embedding-3-small')

_client = OpenAI(api_key=API_KEY) if OpenAI and API_KEY else None

class OpenAIFile:
    """Mock file object for parity with Gemini's File API."""
    def __init__(self, name: str, mime_type: str, b64_data: Optional[str] = None):
        self.name = name
        self.mime_type = mime_type
        self.b64_data = b64_data

def is_configured() -> bool:
    return _client is not None

def get_default_model() -> str:
    return DEFAULT_MODEL

def _ensure_configured() -> None:
    if not is_configured():
        raise RuntimeError('OpenAI API key is not configured. Set OPENAI_API_KEY.')

def generate_content(
    contents: Union[str, List[Any]],
    model: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Any:
    _ensure_configured()
    selected_model = model or DEFAULT_MODEL
    
    # Standardize Gemini-like content list to OpenAI content list
    messages_content: List[Dict[str, Any]] = []
    
    if isinstance(contents, list):
        for part in contents:
            if isinstance(part, str):
                messages_content.append({"type": "text", "text": part})
            elif isinstance(part, OpenAIFile):
                if part.mime_type.startswith("image/"):
                    messages_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{part.mime_type};base64,{part.b64_data}"}
                    })
                elif part.mime_type == 'application/pdf':
                    messages_content.append({
                        "type": "text",
                        "text": f"--- FILE: {part.name} ---\n{part.b64_data}\n--- END FILE ---"
                    })
            elif hasattr(part, 'text'):
                messages_content.append({"type": "text", "text": part.text})
            else:
                messages_content.append({"type": "text", "text": str(part)})
    else:
        messages_content.append({"type": "text", "text": str(contents)})

    is_reasoning_model = selected_model.startswith(('o1', 'o3', 'o4', 'gpt-5', 'gpt-6'))
    
    request_payload: Dict[str, Any] = {
        'model': selected_model,
        'messages': [{"role": "user", "content": messages_content}],
        'max_completion_tokens': (config or {}).get('max_output_tokens', 4096),
    }

    if not is_reasoning_model:
        request_payload['temperature'] = (config or {}).get('temperature', 0.2)

    # support more fields from config
    for k in ['top_p', 'frequency_penalty', 'presence_penalty']:
        if config and k in config and not is_reasoning_model:
            request_payload[k] = config[k]

    if (config or {}).get('response_mime_type') == 'application/json':
        request_payload['response_format'] = {"type": "json_object"}

    response = _client.chat.completions.create(**request_payload)
    if not response.choices:
        raise ValueError('OpenAI không trả về phản hồi.')
    choice = response.choices[0]
    if choice.finish_reason == 'length':
        raise ValueError('Phản hồi OpenAI bị cắt do hết giới hạn token.')
    if choice.finish_reason == 'content_filter' or choice.message.refusal:
        raise ValueError('OpenAI không thể trả lời yêu cầu này.')
    content_text = (choice.message.content or '').strip()
    if not content_text:
        raise ValueError('OpenAI trả về nội dung rỗng.')
    
    # Return an object with a .text attribute for parity with Gemini response
    return type('OpenAIResponse', (), {'text': content_text})

def embed_content(
    content: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = 768,
    model: Optional[str] = None,
    use_cache: bool = False,
    cache_ttl: Optional[int] = None,
) -> List[float]:
    _ensure_configured()
    selected_model = model or EMBED_MODEL

    # text-embedding-3-* support 'dimensions' parameter
    kwargs = {
        "input": str(content),
        "model": selected_model,
    }
    
    if "text-embedding-3" in selected_model:
        kwargs["dimensions"] = output_dimensionality

    response = _client.embeddings.create(**kwargs)
    vector = response.data[0].embedding
    
    if vector is None:
        raise ValueError('Embedding data not found in OpenAI response.')

    return list(vector)

def upload_file(path: str, mime_type: str | None = None) -> OpenAIFile:
    """Prepares a file for vision/chat by encoding to base64."""
    _ensure_configured()
    if not os.path.exists(path):
        raise FileNotFoundError(f'File not found: {path}')

    # For images, we read and encode as base64 to be used directly in chat content
    ext = os.path.splitext(path)[1].lower()
    if not mime_type:
        if ext in ('.jpg', '.jpeg'): mime_type = 'image/jpeg'
        elif ext == '.png': mime_type = 'image/png'
        elif ext == '.webp': mime_type = 'image/webp'
        elif ext == '.pdf': mime_type = 'application/pdf'
        else: mime_type = 'application/octet-stream'

    b64_data = None
    if mime_type.startswith('image/'):
        with open(path, 'rb') as f:
            b64_data = base64.b64encode(f.read()).decode('utf-8')
    elif mime_type == 'application/pdf':
        # For now, we'll extract text from PDF to send via Chat API
        # since Assistant API is more complex for this stateless wrapper.
        try:
            import fitz
            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            # OpenAI text truncation: 128k tokens ~= 500k chars. 
            # Safe limit for input text is around 400k chars.
            if len(text) > 400000:
                print(f"[OpenAI] PDF text too long ({len(text)} chars). Truncating to 400k.")
                text = text[:400000] + "\n[TRUNCATED...]"
            b64_data = text # Store text in b64_data field temporarily for PDFs
        except Exception as e:
            print(f"Error extracting text from PDF in openai_client: {e}")
    
    return OpenAIFile(name=os.path.basename(path), mime_type=mime_type, b64_data=b64_data)

def delete_file(file_name: str) -> None:
    # No-op for OpenAI in this simplified vision-over-chat implementation
    pass

def list_models() -> List[str]:
    _ensure_configured()
    if _client is None: return []
    models = _client.models.list()
    return [m.id for m in models.data]
