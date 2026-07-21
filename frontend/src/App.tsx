import { useEffect, useState } from "react";
import {
  Activity,
  CircleUserRound,
  Clapperboard,
  Film,
  Library,
  Radio,
  Server,
  Tv,
} from "lucide-react";

type Session = {
  session_id: string;
  user_name: string;
  client: string;
  device_name: string;
  title: string;
  series_name?: string;
  season_name?: string;
  episode_number?: number;
  progress_percent: number;
  is_paused: boolean;
  play_method: string;
  video_codec?: string;
  image_url?: string;
};

type Dashboard = {
  server: {
    name: string;
    version: string;
    operating_system: string;
  };
  counts: {
    movies: number;
    series: number;
    episodes: number;
    songs: number;
    albums: number;
  };
  users: {
    total: number;
    disabled: number;
  };
  activity: {
    active_streams: number;
    recorded_events_30d: number;
    play_starts_30d: number;
  };
  sessions: Session[];
};

const number = new Intl.NumberFormat();

function StatCard({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <article className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div>
        <p className="eyebrow">{label}</p>
        <p className="stat-value">{value}</p>
        {detail && <p className="muted">{detail}</p>}
      </div>
    </article>
  );
}

function SessionCard({ session }: { session: Session }) {
  const subtitle = session.series_name
    ? `${session.series_name}${session.season_name ? ` · ${session.season_name}` : ""}${
        session.episode_number ? ` · Episode ${session.episode_number}` : ""
      }`
    : session.title;

  return (
    <article className="session-card">
      <div className="poster">
        {session.image_url ? (
          <img src={session.image_url} alt="" />
        ) : (
          <Clapperboard size={38} />
        )}
      </div>

      <div className="session-content">
        <div className="session-heading">
          <div>
            <p className="session-title">{session.title}</p>
            <p className="muted">{subtitle}</p>
          </div>
          <span className={`pill ${session.play_method.toLowerCase()}`}>
            {session.play_method}
          </span>
        </div>

        <div className="progress-track">
          <div
            className="progress-bar"
            style={{ width: `${Math.max(0, Math.min(session.progress_percent, 100))}%` }}
          />
        </div>

        <div className="session-meta">
          <span>{session.user_name}</span>
          <span>{session.device_name}</span>
          <span>{session.client}</span>
          <span>{session.is_paused ? "Paused" : `${session.progress_percent}%`}</span>
        </div>
      </div>
    </article>
  );
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function load() {
    try {
      const response = await fetch("/api/dashboard");
      if (!response.ok) {
        throw new Error(`Dashboard request returned ${response.status}`);
      }
      setData(await response.json());
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <main>
      <header className="topbar">
        <div className="brand">
          <div className="logo-mark"><Activity size={23} /></div>
          <div>
            <h1>JellyGulp</h1>
            <p>Media intelligence for Jellyfin</p>
          </div>
        </div>

        <div className="status">
          <span className={`status-dot ${error ? "offline" : ""}`} />
          {error ? "Connection issue" : "Jellyfin online"}
        </div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">SERVER OVERVIEW</p>
          <h2>{data?.server.name || "Loading Jellyfin…"}</h2>
          <p className="hero-copy">
            {data
              ? `Jellyfin ${data.server.version} · ${data.server.operating_system}`
              : "Connecting to the JellyGulp backend."}
          </p>
        </div>
        <div className="updated">
          Updated {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
        </div>
      </section>

      {error && (
        <section className="error-panel">
          <strong>JellyGulp could not load the dashboard.</strong>
          <span>{error}</span>
        </section>
      )}

      <section className="stats-grid">
        <StatCard
          icon={<Radio size={22} />}
          label="Active streams"
          value={data?.activity.active_streams ?? "—"}
          detail="Live right now"
        />
        <StatCard
          icon={<Film size={22} />}
          label="Movies"
          value={data ? number.format(data.counts.movies) : "—"}
          detail={`${data ? number.format(data.counts.episodes) : "—"} episodes`}
        />
        <StatCard
          icon={<Tv size={22} />}
          label="Series"
          value={data ? number.format(data.counts.series) : "—"}
          detail="Across all libraries"
        />
        <StatCard
          icon={<CircleUserRound size={22} />}
          label="Users"
          value={data?.users.total ?? "—"}
          detail={`${data?.users.disabled ?? "—"} disabled`}
        />
        <StatCard
          icon={<Library size={22} />}
          label="Play starts"
          value={data?.activity.play_starts_30d ?? "—"}
          detail="Recorded in 30 days"
        />
        <StatCard
          icon={<Server size={22} />}
          label="Events stored"
          value={data?.activity.recorded_events_30d ?? "—"}
          detail="Starts, pauses and stops"
        />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">LIVE ACTIVITY</p>
            <h3>Currently watching</h3>
          </div>
          <span className="count-badge">{data?.sessions.length ?? 0}</span>
        </div>

        <div className="session-list">
          {data?.sessions.length ? (
            data.sessions.map((session) => (
              <SessionCard key={session.session_id} session={session} />
            ))
          ) : (
            <div className="empty-state">
              <Radio size={34} />
              <h4>No active streams</h4>
              <p>Start playing something in Jellyfin and it will appear here.</p>
            </div>
          )}
        </div>
      </section>

      <footer>
        JellyGulp v0.1 · Live dashboard foundation
      </footer>
    </main>
  );
}
