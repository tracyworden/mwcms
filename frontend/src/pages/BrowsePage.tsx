import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';
import { useAuth } from '../hooks/useAuth';
import ThumbnailGrid from '../components/ThumbnailGrid';
import SortFilterControls from '../components/SortFilterControls';
import type { YearsResponse, MediaListResponse, MediaItemSummary } from '../types/media';

const PAGE_SIZE = 20;

interface YearSection {
  year: string;
  items: MediaItemSummary[];
  page: number;
  total: number;
  nextPage: number | null;
  loading: boolean;
}

export default function BrowsePage() {
  const { logout } = useAuth();
  const [years, setYears] = useState<string[]>([]);
  const [activeYear, setActiveYear] = useState<string | null>(null);
  const [sections, setSections] = useState<Map<string, YearSection>>(new Map());
  const [loadingYears, setLoadingYears] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function fetchYears() {
      try {
        const res = await client.get<YearsResponse>('/media/years');
        if (cancelled) return;
        setYears(res.data.years);
        if (res.data.years.length > 0) setActiveYear(res.data.years[0]);
      } catch {
        if (!cancelled) setError('Failed to load years.');
      } finally {
        if (!cancelled) setLoadingYears(false);
      }
    }
    void fetchYears();
    return () => { cancelled = true; };
  }, []);

  const fetchYearPage = useCallback(async (year: string, page: number) => {
    setSections((prev) => {
      const next = new Map(prev);
      const existing = next.get(year);
      if (existing) {
        next.set(year, { ...existing, loading: true });
      } else {
        next.set(year, { year, items: [], page: 0, total: 0, nextPage: null, loading: true });
      }
      return next;
    });

    try {
      const res = await client.get<MediaListResponse>(
        `/media/years/${encodeURIComponent(year)}`,
        { params: { page, page_size: PAGE_SIZE } },
      );
      setSections((prev) => {
        const next = new Map(prev);
        const existing = next.get(year);
        const prevItems = existing?.items ?? [];
        next.set(year, {
          year,
          items: page === 1 ? res.data.items : [...prevItems, ...res.data.items],
          page: res.data.page,
          total: res.data.total,
          nextPage: res.data.next_page,
          loading: false,
        });
        return next;
      });
    } catch {
      setSections((prev) => {
        const next = new Map(prev);
        const existing = next.get(year);
        if (existing) {
          next.set(year, { ...existing, loading: false });
        }
        return next;
      });
    }
  }, []);

  useEffect(() => {
    if (activeYear && !sections.has(activeYear)) {
      void fetchYearPage(activeYear, 1);
    }
  }, [activeYear, sections, fetchYearPage]);

  const handleLoadMore = (year: string) => {
    const section = sections.get(year);
    if (section?.nextPage) {
      void fetchYearPage(year, section.nextPage);
    }
  };

  const handleYearClick = (year: string) => {
    setActiveYear(year);
    if (!sections.has(year)) {
      void fetchYearPage(year, 1);
    }
  };

  const section = activeYear ? sections.get(activeYear) : undefined;

  return (
    <>
      <header className="app-header">
        <h1>Our Family Media</h1>
        <button className="btn" onClick={() => void logout()}>Log out</button>
      </header>

      <div className="browse-layout">
        <aside className="sidebar">
          <div className="sidebar-section">
            <SortFilterControls />
          </div>

          <div className="sidebar-section">
            <h3>Years</h3>
            {loadingYears && <p className="muted">Loading…</p>}
            <ul className="year-list">
              {years.map((year) => (
                <li key={year}>
                  <button
                    className={`year-item${activeYear === year ? ' active' : ''}`}
                    onClick={() => handleYearClick(year)}
                  >
                    {year === 'unknown_year' ? 'Unknown Year' : year}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <main className="content-area">
          {error && <p role="alert" className="error-box">{error}</p>}

          {!loadingYears && years.length === 0 && !error && (
            <p className="muted">No media found.</p>
          )}

          {activeYear && (
            <section className="year-section">
              <h2>{activeYear === 'unknown_year' ? 'Unknown Year' : activeYear}</h2>

              {section ? (
                <>
                  <ThumbnailGrid items={section.items} year={activeYear} />
                  {section.loading && <p className="muted">Loading…</p>}
                  {section.nextPage && !section.loading && (
                    <button
                      className="btn load-more-btn"
                      onClick={() => handleLoadMore(activeYear)}
                    >
                      Load more ({section.items.length} of {section.total})
                    </button>
                  )}
                </>
              ) : (
                <p className="muted">Loading…</p>
              )}
            </section>
          )}
        </main>
      </div>
    </>
  );
}
