import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import client from '../api/client';
import type { MediaItemDetail } from '../types/media';

export default function DetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const year = searchParams.get('year') ?? '';
  const navigate = useNavigate();

  const [detail, setDetail] = useState<MediaItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const videoRef = useRef<HTMLVideoElement>(null);
  const retryCount = useRef(0);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    try {
      const res = await client.get<MediaItemDetail>(`/media/items/${id}`, {
        params: year ? { year } : undefined,
      });
      setDetail(res.data);
      setError('');
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 404) {
        setError('This media item could not be found.');
      } else {
        setError('Failed to load media details.');
      }
    } finally {
      setLoading(false);
    }
  }, [id, year]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  const handleVideoError = useCallback(async () => {
    if (retryCount.current >= 1) return;
    retryCount.current += 1;
    try {
      const res = await client.get<MediaItemDetail>(`/media/items/${id}`, {
        params: year ? { year } : undefined,
      });
      setDetail(res.data);
      if (videoRef.current) {
        videoRef.current.src = res.data.presigned_url;
        videoRef.current.load();
      }
    } catch { /* leave error state */ }
  }, [id, year]);

  if (loading) return <div className="detail-page"><p className="muted">Loading…</p></div>;

  if (error) {
    return (
      <div className="detail-page">
        <button className="btn" onClick={() => navigate('/')}>← Back</button>
        <p role="alert" className="error-box" style={{ marginTop: '1rem' }}>{error}</p>
      </div>
    );
  }

  if (!detail) return null;

  const { metadata } = detail;

  return (
    <div className="detail-page">
      <button className="btn btn-ghost" onClick={() => navigate('/')}>← Back</button>

      <h1>{detail.title}</h1>

      <div className="detail-video">
        <video
          ref={videoRef}
          controls
          src={detail.presigned_url}
          onError={() => void handleVideoError()}
        >
          Your browser does not support the video element.
        </video>
      </div>

      <div className="detail-panels">
        <section className="detail-panel">
          <h2>Transcript</h2>
          {detail.transcript_available && detail.transcript ? (
            <div className="transcript-scroll">
              <Markdown>{detail.transcript}</Markdown>
            </div>
          ) : (
            <p className="muted">No transcript available</p>
          )}
        </section>

        <section className="detail-panel">
          <h2>Metadata</h2>
          {metadata ? (
            <dl className="meta-list">
              {metadata.title && (
                <><dt>Title</dt><dd>{metadata.title}</dd></>
              )}
              {metadata.upload_date && (
                <><dt>Upload Date</dt><dd>{metadata.upload_date}</dd></>
              )}
              {metadata.playlists && metadata.playlists.trim() !== '' && (
                <><dt>Playlists</dt><dd>{metadata.playlists}</dd></>
              )}
              {metadata.transcript_language && (
                <><dt>Language</dt><dd>{metadata.transcript_language}</dd></>
              )}
              {metadata.description && (
                <><dt>Description</dt><dd>{metadata.description}</dd></>
              )}
              {metadata.url && (
                <><dt>Original URL</dt><dd><a href={metadata.url} target="_blank" rel="noopener noreferrer">{metadata.url}</a></dd></>
              )}
            </dl>
          ) : (
            <p className="muted">No metadata available</p>
          )}

          <button
            className="btn"
            disabled
            title="Description editing planned for a future release"
          >
            Edit Description
          </button>
        </section>
      </div>
    </div>
  );
}
