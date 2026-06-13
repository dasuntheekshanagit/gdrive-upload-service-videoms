# GDrive Upload Service (FastAPI)

This service provides an alternative flow for uploading large video files from Google Drive to S3.

## Features
- **FastAPI Endpoint:** `/api/gdrive-upload`
- **Large File Handling:** Uses `rclone` to stream files directly from GDrive to S3.
- **Asynchronous:** Transfers run in the background.
- **Integration:** Updates the shared database, sends SQS messages, and wakes up the transcoding EC2 instance.

## Setup Instructions

### 1. Rclone Configuration
You need an `rclone.conf` file in the project root. At minimum, it must define the `gdrive` and `s3` remotes.

**Example `rclone.conf`:**
```ini
[gdrive]
type = drive
scope = drive.readonly
# You will need to run 'rclone config' locally to generate tokens for this section

[s3]
type = s3
provider = AWS
region = eu-north-1
# rclone will use environment variables for credentials if these are omitted
```

### 2. Environment Variables
Create a `.env` file or export the following:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### 3. Running with Docker Compose
```bash
docker-compose up -d --build
```

## API Usage

**POST** `/api/gdrive-upload`

**Request Body:**
```json
{
  "gdriveUrl": "https://drive.google.com/file/d/YOUR_FILE_ID/view",
  "userId": "user-123",
  "email": "user@example.com",
  "folderId": "optional-folder-uuid",
  "originalFileName": "my_large_video.mp4",
  "description": "Video from GDrive",
  "resolutions": ["1080p", "720p"],
  "segmentDuration": 10
}
```

## Architecture
1. **Metadata:** Saved to `video_metadata` table with status `TRANSFERRING_TO_S3`.
2. **Transfer:** `rclone backend copyid` streams file to S3.
3. **Completion:** Status set to `UPLOADED`.
4. **Trigger:** SQS message sent and EC2 instance `i-03a1d1cb5ad9dece8` is started.
