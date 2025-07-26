# TTS Service API Integration Guide

## Quick Start

**Service URL**: `http://10.0.0.46:5000`

## API Endpoint

### POST /transcribe

Transcribe audio files using GPU-accelerated faster-whisper.

**URL**: `POST http://10.0.0.46:5000/transcribe`

**Content-Type**: `multipart/form-data`

### Request Format

- **Field Name**: `file` (required)
- **File Types**: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm (including video formats like video/webm for browser audio recording)
- **Max File Size**: 100MB

### Example Request

```bash
curl -X POST "http://10.0.0.46:5000/transcribe" \
  -F "file=@your-audio-file.mp3"
```

### Response Format

**Success (HTTP 200)**:
```json
{
  "text": "Your transcribed text here"
}
```

**Error (HTTP 400/500)**:
```json
{
  "message": "Error description"
}
```

## Status Endpoints

- **Health Check**: `GET /health`
- **Service Status**: `GET /status`
- **Preload Model**: `POST /preload`

## Integration Notes

- **Single Request**: Service processes one request at a time
- **Model Loading**: First request loads the model (~25 seconds), subsequent requests are fast
- **Preload Model**: Use `/preload` endpoint to start model loading before transcription
- **GPU Required**: Service uses CUDA for GPU acceleration
- **Auto Cleanup**: Temporary files are automatically cleaned up

## Preload Endpoint

### POST /preload

Preload the Whisper model asynchronously to improve response times.

**URL**: `POST http://10.0.0.46:5000/preload`

**Response Format**:

**Success (HTTP 200)**:
```json
{
  "status": "success",
  "message": "Model preloaded successfully",
  "model": "small",
  "device": "cuda"
}
```

**Already Loaded (HTTP 200)**:
```json
{
  "status": "success",
  "message": "Model already loaded",
  "model": "small",
  "device": "cuda"
}
```

**Already Preloading (HTTP 200)**:
```json
{
  "status": "success",
  "message": "Model preloading already in progress",
  "model": "small",
  "device": "cuda"
}
```

**Error (HTTP 500)**:
```json
{
  "status": "error",
  "message": "Failed to preload model: Error description",
  "model": "small",
  "device": "cuda"
}
```

### Example Preload Request

```bash
curl -X POST "http://10.0.0.46:5000/preload"
```

## Error Codes

- **400**: Bad request (missing file, invalid format, file too large)
- **429**: Service busy (try again later)
- **500**: Server error (transcription failure)

## Example Integration (JavaScript)

```javascript
const formData = new FormData();
formData.append('file', audioFile);

const response = await fetch('http://10.0.0.46:5000/transcribe', {
  method: 'POST',
  body: formData
});

if (response.ok) {
  const result = await response.json();
  console.log('Transcribed text:', result.text);
} else {
  const error = await response.json();
  console.error('Error:', error.message);
}
```

## Configuration

Default settings (can be modified via environment variables):
- **Model**: small
- **Device**: cuda (GPU)
- **Port**: 5000
- **Max File Size**: 100MB 