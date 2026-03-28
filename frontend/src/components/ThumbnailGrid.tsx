import { useNavigate } from 'react-router-dom';
import type { MediaItemSummary } from '../types/media';

interface ThumbnailGridProps {
  items: MediaItemSummary[];
  year: string;
}

function PlaceholderSvg() {
  return (
    <svg
      viewBox="0 0 160 90"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="No thumbnail available"
      role="img"
    >
      <rect width="160" height="90" fill="var(--color-placeholder-bg)" />
      <polygon points="72,30 72,60 95,45" fill="var(--color-placeholder-icon)" />
      <text x="80" y="80" textAnchor="middle" fill="var(--color-placeholder-icon)"
        fontSize="8" fontFamily="var(--font-sans)">No thumbnail</text>
    </svg>
  );
}

export default function ThumbnailGrid({ items, year }: ThumbnailGridProps) {
  const navigate = useNavigate();

  if (items.length === 0) {
    return <p className="muted">No items in this year.</p>;
  }

  return (
    <div className="thumb-grid">
      {items.map((item) => (
        <button
          key={item.id}
          className="thumb-card"
          onClick={() => navigate(`/detail/${item.id}?year=${encodeURIComponent(year)}`)}
          aria-label={`View ${item.title}`}
        >
          <div className="thumb-card__image">
            {item.has_thumbnail && item.thumbnail_url ? (
              <img src={item.thumbnail_url} alt={item.title} loading="lazy" />
            ) : (
              <PlaceholderSvg />
            )}
          </div>
          <div className="thumb-card__title" title={item.title}>
            {item.title}
          </div>
        </button>
      ))}
    </div>
  );
}
