export interface MediaItemSummary {
  id: string;
  title: string;
  year: string;
  upload_date: string;
  media_type: string;
  thumbnail_url: string | null;
  has_thumbnail: boolean;
}

export interface MetadataAttributes {
  video_id: string;
  title: string;
  url: string;
  upload_date: string;
  playlists: string | null;
  transcript_language: string | null;
  processed_timestamp: string | null;
  description: string | null;
  last_modified_by?: string | null;
  schema_version?: string | null;
  [key: string]: unknown;
}

export interface MediaItemDetail {
  id: string;
  title: string;
  year: string;
  media_type: string;
  presigned_url: string;
  thumbnail_url: string | null;
  metadata: MetadataAttributes | null;
  transcript: string | null;
  transcript_available: boolean;
}

export interface MediaListResponse {
  items: MediaItemSummary[];
  page: number;
  page_size: number;
  total: number;
  next_page: number | null;
}

export interface YearsResponse {
  years: string[];
}

export interface LoginResponse {
  token: string;
}
