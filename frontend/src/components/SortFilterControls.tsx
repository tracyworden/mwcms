const mediaTypes = [
  { label: 'Video', enabled: true },
  { label: 'Images', enabled: false },
  { label: 'Audio', enabled: false },
];

const sortOptions = [
  { label: 'By Date', value: 'date', enabled: true },
  { label: 'By Name', value: 'name', enabled: false },
  { label: 'By Duration', value: 'duration', enabled: false },
];

export default function SortFilterControls() {
  return (
    <>
      <h3>Media Type</h3>
      <div className="filter-group" role="tablist" aria-label="Media type filter">
        {mediaTypes.map((type) => (
          <button
            key={type.label}
            role="tab"
            aria-selected={type.enabled}
            disabled={!type.enabled}
            title={type.enabled ? undefined : 'Coming soon'}
            className={`filter-tab${type.enabled ? ' active' : ''}`}
          >
            {type.label}
          </button>
        ))}
      </div>

      <h3>Sort</h3>
      <select className="select" aria-label="Sort order" defaultValue="date">
        {sortOptions.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={!opt.enabled}>
            {opt.label}{!opt.enabled ? ' (coming soon)' : ''}
          </option>
        ))}
      </select>
    </>
  );
}
