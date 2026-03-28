# Implementation Plan: Family Media Viewer

## Overview

Incremental build of a FastAPI + React SPA for browsing S3-stored family videos. Backend first (auth, listing, detail, config, health), then frontend components, then Docker packaging. Property tests and unit tests are sub-tasks under their related implementation tasks.

## Tasks

- [x] 1. Python environment and project scaffolding
  - [x] 1.1 Create Python virtual environment
    - Run `python -m venv venv` at the project root
    - Create `requirements.txt` with: fastapi, uvicorn, boto3, bcrypt, python-jose[cryptography], pydantic, pydantic-settings, hypothesis, pytest, pytest-asyncio, moto[s3,dynamodb], httpx
    - Install dependencies into the venv via `pip install -r requirements.txt`
    - _Requirements: 10.1_

  - [x] 1.2 Create backend project structure and config module
    - Create directory layout: `app/`, `app/api/`, `app/api/auth/`, `app/api/media/`, `app/api/health/`, `app/api/config/`, `app/api/s3/`, `app/cli/`, `tests/`, `tests/property/`, `tests/unit/`
    - Implement `app/api/config/media_config.py` with `MediaSourceConfig` dataclass and `MEDIA_SOURCES` dict loaded from env vars
    - Implement `app/api/config/settings.py` using pydantic-settings `BaseSettings` to load `S3_BUCKET_NAME`, `AWS_REGION`, `SESSION_SECRET`, `DYNAMODB_TABLE_NAME`
    - Create `app/main.py` with FastAPI app instance, CORS middleware, and static file mount placeholder
    - _Requirements: 9.1, 9.2, 9.4, 10.2_

  - [ ]* 1.3 Write property tests for config loading (Properties 13, 14)
    - **Property 13: Media source config lookup** — For any configured media type key, lookup returns correct bucket, extension, suffixes. Unconfigured key fails gracefully.
    - **Property 14: Environment variable config loading** — For any set of env vars, the settings object fields match the provided values exactly.
    - **Validates: Requirements 9.1, 9.4, 10.2**

  - [ ]* 1.4 Write unit tests for config module
    - Test default media source config has `video` entry with correct values
    - Test settings loads from environment variables
    - _Requirements: 9.1, 9.2, 10.2_

- [x] 2. Checkpoint — Verify project scaffolding
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Auth module
  - [x] 3.1 Implement DynamoDB user model and CLI create-user command
    - Create `app/api/auth/models.py` with user schema (username PK, password_hash)
    - Create `app/cli/create_user.py` as `python -m app.cli.create_user <username> <password>` that writes bcrypt-hashed record to DynamoDB User_Table
    - _Requirements: 1.6, 1.7_

  - [x] 3.2 Implement login endpoint and JWT auth dependency
    - Create `app/api/auth/router.py` with `POST /api/auth/login` — verify bcrypt hash against DynamoDB, return HS256 JWT with `sub`, `exp` (24h), `iat`
    - Create `app/api/auth/dependencies.py` with FastAPI dependency that validates Bearer JWT on `/api/media/*` routes
    - Create `POST /api/auth/logout` — returns 200 (client-side token clearing)
    - _Requirements: 1.1, 1.2, 1.5_

  - [ ]* 3.3 Write property tests for auth (Properties 1, 2, 3)
    - **Property 1: Authentication round-trip** — For any username/password, create-user then login returns JWT with correct `sub` and future `exp`.
    - **Property 2: Invalid credentials return uniform error** — For any non-existent user or wrong password, login returns same error shape with no field-specific detail.
    - **Property 3: Invalid tokens are rejected** — For any expired, malformed, or arbitrary string token, protected endpoints return 401.
    - **Validates: Requirements 1.1, 1.2, 1.5, 1.6**

  - [ ]* 3.4 Write unit tests for auth
    - Test login with valid credentials returns 200 + JWT
    - Test login with wrong password returns 401
    - Test missing Bearer header returns 401
    - Test expired token returns 401
    - _Requirements: 1.1, 1.2, 1.5_

- [x] 4. Checkpoint — Verify auth module
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. S3 access layer and media listing
  - [x] 5.1 Implement S3 access layer with TTL cache
    - Create `app/api/s3/client.py` — generic S3 operations: list prefixes, list objects by prefix, generate presigned URL, get object content
    - Implement in-memory TTL cache (60s) for year listing and per-year item listings
    - All operations parameterized by bucket name from media source config
    - _Requirements: 2.2, 2.3, 9.1_

  - [x] 5.2 Implement year listing endpoint
    - Create `app/api/media/router.py` with `GET /api/media/years` — list year-folder prefixes, sort reverse chronological with `unknown_year` last
    - Return `YearsResponse` model
    - Return 503 if S3 unreachable
    - _Requirements: 2.1, 2.2, 2.7, 2.8_

  - [x] 5.3 Implement paginated media listing endpoint
    - `GET /api/media/years/{year}?page=N&page_size=M&sort=date&type=video`
    - List `.mp4` objects in year prefix, check for companion `.jpg` thumbnail, generate presigned thumbnail URLs
    - Return `MediaListResponse` with `items`, `page`, `page_size`, `total`, `next_page`
    - Validate `sort` param — only `date` accepted, else 400
    - _Requirements: 2.3, 2.5, 3.1, 8.3, 8.4_

  - [ ]* 5.4 Write property tests for listing (Properties 4, 5, 6, 12)
    - **Property 4: Year listing sort order** — For any set of year prefixes including `unknown_year`, returned order is reverse chronological with `unknown_year` last.
    - **Property 5: Pagination bounds** — For N items, page P, size S: at most S items returned, total=N, next_page correct, all items in requested year.
    - **Property 6: Thumbnail URL conditional inclusion** — `has_thumbnail` true and `thumbnail_url` non-null iff `.jpg` exists; false and null otherwise.
    - **Property 12: Invalid sort parameter rejection** — For any sort value != `date`, returns 400 with supported values listed.
    - **Validates: Requirements 2.1, 2.2, 2.3, 3.1, 8.4**

  - [ ]* 5.5 Write unit tests for listing
    - Test year listing returns sorted years with `unknown_year` last
    - Test pagination with various page sizes
    - Test empty year folder returns empty items list
    - Test S3 unreachable returns 503
    - _Requirements: 2.1, 2.2, 2.3, 2.8_

- [x] 6. Checkpoint — Verify listing endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Media detail, transcript, and metadata
  - [x] 7.1 Implement media detail endpoint
    - `GET /api/media/items/{id}` — generate presigned URL for `.mp4`, read metadata JSON, read transcript `.md`, check thumbnail `.jpg`
    - Return `MediaItemDetail` model
    - Return 404 if `.mp4` does not exist
    - Graceful degradation: metadata read failure → `metadata: null`, transcript read failure → `transcript: null, transcript_available: false` with error indicator
    - _Requirements: 4.1, 4.2, 4.5, 5.1, 5.4, 6.1, 6.3_

  - [x] 7.2 Implement Pydantic models for metadata
    - Create `app/api/media/models.py` with `MetadataAttributes` (extra="allow"), `MetadataFile`, `MediaItemSummary`, `MediaItemDetail`, `MediaListResponse`, `YearsResponse`, `MetadataUpdateRequest`
    - Include optional future fields: `last_modified_by`, `schema_version`
    - Preserve `upload_date` as YYYYMMDD string, preserve `url` as original YouTube URL
    - _Requirements: 6.1, 6.4, 6.5, 6.6, 7.5_

  - [x] 7.3 Implement metadata update stub endpoint
    - `PATCH /api/media/items/{id}/metadata` — validate payload has `description` string field (422 if not), then return 501
    - _Requirements: 7.3, 7.4_

  - [ ]* 7.4 Write property tests for detail and metadata (Properties 7, 8, 9, 10, 11)
    - **Property 7: Presigned URL correctness** — Returned URL references correct bucket/key, expiration ≤ 3600s.
    - **Property 8: Missing media returns 404** — Non-existent item ID returns 404.
    - **Property 9: Transcript conditional inclusion** — `transcript_available` true and `transcript` non-empty iff `.md` exists; false and null otherwise.
    - **Property 10: Metadata fidelity** — All fields preserved exactly: `upload_date` as YYYYMMDD, `url` as original YouTube URL, unknown extra fields included.
    - **Property 11: Metadata update stub validation** — Valid `description` string → 501; missing/non-string `description` → 422.
    - **Validates: Requirements 4.1, 4.2, 4.5, 5.1, 6.1, 6.4, 6.5, 6.6, 7.3, 7.4**

  - [ ]* 7.5 Write unit tests for detail and metadata
    - Test detail for existing item returns full response with presigned URL, metadata, transcript
    - Test detail for non-existent item returns 404
    - Test metadata with unknown extra fields preserves them
    - Test transcript unavailable returns null with indicator
    - Test metadata update stub with valid payload returns 501
    - Test metadata update stub with missing description returns 422
    - _Requirements: 4.1, 4.5, 5.1, 5.4, 6.1, 6.6, 7.3, 7.4_

- [x] 8. Health endpoint
  - [x] 8.1 Implement health check endpoint
    - `GET /health` — check S3 `head_bucket` and DynamoDB `describe_table`
    - Return 200 with `{"s3": "ok", "dynamodb": "ok"}` when both pass
    - Return 503 with details on which dependency failed
    - _Requirements: 10.3, 10.4_

  - [ ]* 8.2 Write unit tests for health endpoint
    - Test healthy state returns 200
    - Test S3 down returns 503 with `s3: unreachable`
    - Test DynamoDB down returns 503 with `dynamodb: unreachable`
    - _Requirements: 10.3, 10.4_

- [x] 9. Checkpoint — Verify all backend endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. React frontend scaffolding
  - [x] 10.1 Initialize React app and project structure
    - Create React app (Vite + TypeScript) in `frontend/`
    - Install dependencies: react-router-dom, react-markdown, axios
    - Create directory layout: `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/api/`, `frontend/src/hooks/`, `frontend/src/types/`
    - Create `frontend/src/api/client.ts` — axios instance with Bearer token injection and 401 interceptor that clears token and redirects to login
    - Create `frontend/src/types/media.ts` — TypeScript interfaces matching backend response shapes
    - _Requirements: 1.3, 10.1_

  - [x] 10.2 Implement login page
    - Create `frontend/src/pages/LoginPage.tsx` — login form, POST to `/api/auth/login`, store JWT in memory (not localStorage)
    - Create auth context/hook for token state management
    - Redirect to login on missing token or 401
    - Implement logout button that clears token and redirects
    - _Requirements: 1.1, 1.3, 1.4, 1.8_

  - [x] 10.3 Implement year browser and thumbnail grid
    - Create `frontend/src/pages/BrowsePage.tsx` — fetch `/api/media/years`, render year groups in reverse chronological order with `unknown_year` last
    - Create `frontend/src/components/ThumbnailGrid.tsx` — render media items as image grid, placeholder SVG when no thumbnail, click navigates to detail
    - Implement pagination (load more or infinite scroll within a year)
    - _Requirements: 2.1, 2.4, 3.2, 3.3_

  - [x] 10.4 Implement media detail view
    - Create `frontend/src/pages/DetailPage.tsx` — HTML5 `<video>` player with presigned URL src, transcript panel (rendered markdown via react-markdown), metadata panel
    - Implement presigned URL refresh: on 403 from S3 during playback, re-fetch detail endpoint for fresh URL
    - Display "No transcript available" when `transcript_available` is false
    - Display "No metadata available" when `metadata` is null
    - Render disabled "Edit Description" button with tooltip "Description editing planned for a future release"
    - _Requirements: 4.1, 4.3, 4.4, 5.2, 5.3, 6.2, 6.3, 6.7, 7.1, 7.2_

  - [x] 10.5 Implement sort and filter controls
    - Create `frontend/src/components/SortFilterControls.tsx`
    - Media type tabs: "Video" enabled, others disabled with "coming soon" tooltip
    - Sort dropdown: "By Date" enabled, "By Name" and "By Duration" disabled with "coming soon" tooltip
    - _Requirements: 2.5, 2.6, 8.1, 8.2_

  - [ ]* 10.6 Write frontend unit tests
    - Test login form submits credentials and stores token on success
    - Test 401 response triggers redirect to login
    - Test disabled sort/filter controls show tooltip on interaction
    - Test placeholder image renders when no thumbnail
    - _Requirements: 1.1, 1.3, 2.6, 3.3, 8.2_

- [x] 11. Checkpoint — Verify frontend components
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Docker packaging and wiring
  - [x] 12.1 Create Dockerfile and wire frontend to backend
    - Multi-stage Dockerfile: build React app, then copy static assets into Python image
    - Configure FastAPI to serve `frontend/dist/` as static files and mount API routes under `/api/`
    - Accept env vars: `S3_BUCKET_NAME`, `AWS_REGION`, `SESSION_SECRET`, `DYNAMODB_TABLE_NAME`
    - Expose single port, run with uvicorn
    - _Requirements: 10.1, 10.2_

  - [x] 12.2 Create `tests/conftest.py` with shared fixtures
    - Mocked S3 via moto with pre-populated test bucket (year folders, .mp4, .metadata.json, .md, .jpg files)
    - Mocked DynamoDB via moto with User_Table and test users
    - FastAPI TestClient fixture with auth helper
    - Test JWT secret
    - _Requirements: 1.1, 2.2, 4.1_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses moto for S3/DynamoDB mocking in all tests
